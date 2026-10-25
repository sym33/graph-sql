"""Compare deployment-cost scenarios from repeated, answer-checked measurements.

Standard-library calculator. A portable JSON measurement table can replace the
included study receipts. Results are sums of phase/task medians, not newly
measured end-to-end times, uncertainty estimates or human-effort measurements.
"""
from pathlib import Path
from collections import defaultdict
import argparse
import gzip
import hashlib
import json
import math
import statistics
ROOT = Path(__file__).resolve().parent

PHASES = ('initial_base', 'initial_stored', 'invalidate', 'refresh_base', 'refresh_stored')


def calculate(table, task_counts, refreshes):
    """Portable schema: arms, load/refresh samples and per-task retrieval samples."""
    if type(refreshes) is not int or refreshes < 0:
        raise ValueError('refreshes must be a nonnegative integer')
    if not task_counts or any(type(n) is not int or n < 0 for n in task_counts.values()):
        raise ValueError('task counts must be nonnegative integers; supply at least one task')
    if table.get('answer_agreement_verified') is not True:
        raise ValueError('Verify complete answer agreement before comparing costs')
    if table.get('schema_version') != 1:
        raise ValueError('Unsupported measurement schema version')
    names = set()
    totals = []
    for arm in table['arms']:
        if type(arm['stored']) is not bool:
            raise ValueError('stored must be Boolean')
        if arm['name'] in names:
            raise ValueError('Duplicate arm name')
        names.add(arm['name'])
        def median(values):
            if not values or any(type(x) not in (float, int) or not math.isfinite(x) or x < 0 for x in values):
                raise ValueError('Samples must be nonempty, finite and nonnegative')
            return statistics.median(values)
        load = median(arm['initial_base_ms'])
        initial_extra = median(arm['initial_stored_ms']) if arm['stored'] else 0
        refresh = median(arm['refresh_base_ms'])
        refresh_extra = (median(arm['invalidate_ms']) + median(arm['refresh_stored_ms'])) if arm['stored'] else 0
        retrieval = {}
        for task, count in task_counts.items():
            if task not in arm['retrieval_ms']:
                raise ValueError(f"Task {task} unavailable in {arm['name']}; use a common task set")
            retrieval[task] = count * median(arm['retrieval_ms'][task])
        totals.append({'arm': arm['name'], 'engine': arm['engine'], 'stored': arm['stored'],
                       'initial_build_ms': load + initial_extra,
                       'refreshes_ms': refreshes * (refresh + refresh_extra),
                       'retrieval_ms': sum(retrieval.values()), 'retrieval_by_task_ms': retrieval,
                       'scenario_total_ms': load + initial_extra + refreshes * (refresh + refresh_extra) + sum(retrieval.values())})
    if not totals:
        raise ValueError('At least one arm is required')
    return {'requests': task_counts, 'refreshes': refreshes,
            'calculation': 'initial base + initial materialization + refreshes*(base replacement + invalidation + rematerialization) + sum(requests*retrieval median)',
            'scope': 'Measured deployment phases and task medians; projected serial costs. No uncertainty, concurrency, scaling or human-effort claim.',
            'measurement_conditions': table.get('conditions', {}), 'arms': totals}


def frozen_table(plan_control=False):
    manifest = {r['path']: r['sha256'] for r in json.loads((ROOT / 'MANIFEST.json').read_text())['files']}
    def observed(name):
        relative = 'Source_Refresh/observed/' + name
        raw = (ROOT / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest.get(relative):
            raise ValueError('Measurement integrity check failed: ' + relative)
        return json.loads(gzip.decompress(raw))
    registered = observed('registered_results.json.gz')
    if not registered['all_complete_outputs_equal'] or registered['stale_outputs'] != 0:
        raise ValueError('Registered output agreement did not pass')
    raw = registered['timings']
    if plan_control:
        control = observed('plan_control.json.gz')
        if not control['all_complete_outputs_equal']:
            raise ValueError('Control output agreement did not pass')
        raw = control['measurements']
    arms = []
    for engine in ('Neo4j', 'SQLite'):
        for stored in (False, True):
            retrieval = defaultdict(list)
            for row in raw:
                if row.get('state', 'October') != 'October' or row['stored'] != stored:
                    continue
                if plan_control:
                    variant = row.get('engine', row.get('variant'))
                    desired = 'Neo4j' if engine == 'Neo4j' else 'SQLite_ordered'
                    if variant != desired:
                        continue
                elif row['engine'] != engine:
                    continue
                retrieval[row['workload']].append(row['milliseconds'])
            if not retrieval:
                raise ValueError('No compatible retrieval samples for ' + engine)
            arm = {'name': engine + (' stored' if stored else ' query-time'), 'engine': engine,
                   'stored': stored, 'retrieval_ms': dict(retrieval)}
            for phase in PHASES:
                arm[phase + '_ms'] = [r['milliseconds'] for r in registered['maintenance'] if r['engine'] == engine and r['phase'] == phase]
            arms.append(arm)
    return {'schema_version': 1, 'answer_agreement_verified': True,
            'conditions': {'retrieval_session': 'exploratory ordered-plan control' if plan_control else 'registered automatic-plan comparison',
                           'source_state': 'later official sources', 'maintenance_session': 'registered full-layer replacement',
                           'loading_paths': 'Neo4j batched HTTP; SQLite local committed inserts',
                           'reuse_assumption': 'The same measured costs apply to each specified full-layer replacement; retrieval uses the later-state workload.'},
            'arms': arms}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='Portable measurement JSON; use your own answer-checked samples.')
    parser.add_argument('--plan-control', action='store_true', help='Use ordered SQLite and Neo4j retrieval from the exploratory control.')
    parser.add_argument('--task', action='append', default=[], metavar='NAME=COUNT', help='Repeat to define a workload mix; default: one witness retrieval.')
    parser.add_argument('--refreshes', type=int, default=1)
    parser.add_argument('--export-input', type=Path, help='Export the portable measurement table.')
    parser.add_argument('--output', type=Path, help='Save the calculated scenario.')
    args = parser.parse_args()
    try:
        if args.input and args.plan_control:
            raise ValueError('Use either a custom input or the frozen plan control')
        table = json.loads(args.input.read_text()) if args.input else frozen_table(args.plan_control)
        counts = {}
        for token in args.task or ['L1_candidates=1']:
            task, count = token.rsplit('=', 1)
            if task in counts:
                raise ValueError('Duplicate task ' + task)
            counts[task] = int(count)
        result = calculate(table, counts, args.refreshes)
        if args.export_input:
            args.export_input.parent.mkdir(parents=True, exist_ok=True)
            args.export_input.write_text(json.dumps(table, indent=2) + '\n')
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
