"""Check portable accounting, invalid inputs and all published later-state totals."""
from pathlib import Path
import subprocess
import tempfile
import shutil
import gzip
import json
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deployment_costs import ROOT, calculate, frozen_table


def fixture():
    def arm(stored):
        return {'name': 'stored' if stored else 'query', 'engine': 'ExampleEngine', 'stored': stored,
                'initial_base_ms': [90, 100, 500], 'initial_stored_ms': [10],
                'refresh_base_ms': [40], 'invalidate_ms': [2], 'refresh_stored_ms': [8],
                'retrieval_ms': {'lookup': [2 if stored else 10], 'explain': [6 if stored else 4]}}
    return {'schema_version': 1, 'answer_agreement_verified': True, 'arms': [arm(False), arm(True)]}


class DeploymentCosts(unittest.TestCase):
    def test_mixed_workload_and_repeated_refresh(self):
        rows = calculate(fixture(), {'lookup': 3, 'explain': 2}, 2)['arms']
        self.assertEqual(rows[0]['scenario_total_ms'], 218)
        self.assertEqual(rows[1]['scenario_total_ms'], 228)
        self.assertEqual(rows[1]['retrieval_ms'], 18)

    def test_zero_requests_and_zero_refresh(self):
        rows = calculate(fixture(), {'lookup': 0}, 0)['arms']
        self.assertEqual([r['scenario_total_ms'] for r in rows], [100, 110])

    def test_materialization_break_even(self):
        rows = calculate(fixture(), {'lookup': 3}, 1)['arms']
        self.assertEqual([r['scenario_total_ms'] for r in rows], [170, 166])

    def test_linear_rescaling_and_arm_order(self):
        table = fixture()
        expected = calculate(table, {'lookup': 3}, 2)['arms']
        for arm in table['arms']:
            for key in ('initial_base_ms', 'initial_stored_ms', 'refresh_base_ms', 'invalidate_ms', 'refresh_stored_ms'):
                arm[key] = [v * 2 for v in arm[key]]
            arm['retrieval_ms'] = {k: [v * 2 for v in values] for k, values in arm['retrieval_ms'].items()}
        table['arms'].reverse()
        scaled = calculate(table, {'lookup': 3}, 2)['arms']
        self.assertEqual({r['arm']: r['scenario_total_ms'] for r in scaled},
                         {r['arm']: 2 * r['scenario_total_ms'] for r in expected})

    def test_reject_unverified_answers(self):
        table = fixture(); table['answer_agreement_verified'] = False
        with self.assertRaises(ValueError): calculate(table, {'lookup': 1}, 1)

    def test_reject_invalid_budgets(self):
        for counts, refreshes in (({'lookup': -1}, 1), ({'lookup': 1.5}, 1), ({'lookup': 1}, -1), ({}, 1)):
            with self.subTest(counts=counts, refreshes=refreshes), self.assertRaises(ValueError):
                calculate(fixture(), counts, refreshes)

    def test_reject_incomplete_or_corrupted_measurements(self):
        for key, value in (('initial_base_ms', []), ('initial_base_ms', [float('nan')]), ('refresh_base_ms', [-1])):
            table = fixture(); table['arms'][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                calculate(table, {'lookup': 1}, 1)
        with self.assertRaises(ValueError): calculate(fixture(), {'absent': 1}, 1)
        table = fixture(); table['arms'][1]['name'] = table['arms'][0]['name']
        with self.assertRaises(ValueError): calculate(table, {'lookup': 1}, 1)

    def test_reproduce_all_recorded_later_state_lifecycle_totals(self):
        receipt = json.loads(gzip.decompress((ROOT / 'Source_Refresh/observed/registered_results.json.gz').read_bytes()))
        table = frozen_table()
        checks = 0
        for recorded in receipt['lifecycle_costs']:
            if recorded['state'] != 'October': continue
            for count, totals in recorded['request_budgets'].items():
                result = calculate(table, {recorded['workload']: int(count)}, 1)
                for row in result['arms']:
                    if row['engine'] == recorded['engine']:
                        expected = totals['stored_ms' if row['stored'] else 'query_time_ms']
                        self.assertAlmostEqual(row['scenario_total_ms'], expected, places=7)
                        checks += 1
        self.assertEqual(checks, 112)

    def test_standalone_transfer_with_non_medication_measurements(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            shutil.copy2(ROOT / 'deployment_costs.py', target / 'calculator.py')
            (target / 'measurements.json').write_text(json.dumps(fixture()))
            output = subprocess.check_output([sys.executable, str(target / 'calculator.py'),
                '--input', str(target / 'measurements.json'), '--task', 'lookup=3',
                '--task', 'explain=2', '--refreshes', '2'])
            actual = json.loads(output)
            self.assertEqual([r['scenario_total_ms'] for r in actual['arms']], [218, 228])
            self.assertEqual({r['engine'] for r in actual['arms']}, {'ExampleEngine'})

    def test_ordered_plan_scenario_and_session_labels(self):
        table = frozen_table(True)
        result = calculate(table, {'L4_cross_source_context': 100}, 1)
        totals = {r['arm']: r['scenario_total_ms'] for r in result['arms']}
        self.assertAlmostEqual(totals['SQLite query-time'], 5295.80682, places=5)
        self.assertAlmostEqual(totals['Neo4j stored'], 17189.743035, places=5)
        self.assertIn('exploratory', result['measurement_conditions']['retrieval_session'])
        self.assertIn('registered', result['measurement_conditions']['maintenance_session'])
        with self.assertRaises(ValueError): calculate(table, {'L1_candidates': 1}, 1)


if __name__ == '__main__': unittest.main()
