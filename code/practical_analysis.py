"""Reconstruct complete documentary follow-up populations in both source states.

Uses included, integrity-checked inputs; needs only Python's standard library.
Actions are deterministic evidence-review categories, not payment decisions.
The later-state reuse and action analysis are exploratory.
"""
from collections import Counter
from pathlib import Path
import argparse
import csv
import gzip
import json
from example import ROOT, load, analyze, follow_up, verified_bytes

POLICIES = ('coarse', 'exact_code', 'explicit_formulation')


def population(snapshot):
    db, records, assess = load(snapshot)
    auths = sorted({r[0] for r in db.execute('''
        SELECT s.authorization FROM sai s JOIN tariff t ON s.code=t.code
        WHERE coalesce(trim(s.code),'') NOT IN ('','NA')
        UNION SELECT s.authorization FROM sai s JOIN sl l ON s.authorization=l.authorization
        JOIN tariff t ON l.code=t.code WHERE coalesce(trim(l.code),'') NOT IN ('','NA')
    ''')})
    answers = [analyze(auth, db, records, assess) for auth in auths]
    db.close()
    rows = {}
    for answer in answers:
        for candidate in answer['candidates']:
            key = ('CH:authorization:' + answer['authorization'], candidate['tariff_record'])
            rows[key] = {'product': key[0], 'product_names': answer['product'],
                         'SAI_records': answer['SAI_records'], **candidate,
                         'follow_up': follow_up(candidate)}
    summary = {'candidates': len(rows), 'authorizations': len(auths),
               'direct_candidates': sum(c['direct_lookup'] for c in rows.values()),
               'additional_candidates': sum(not c['direct_lookup'] for c in rows.values()),
               'status_counts': {p: dict(sorted(Counter(c['judgments'][p] for c in rows.values()).items()))
                                 for p in POLICIES},
               'follow_up_counts': dict(sorted(Counter(c['follow_up'] for c in rows.values()).items()))}
    return rows, summary


def main(output):
    manifest = {r['path']: r['sha256'] for r in json.loads((ROOT / 'MANIFEST.json').read_text())['files']}
    receipt = json.loads(gzip.decompress(verified_bytes('Source_Refresh/observed/registered_results.json.gz', manifest)))
    before, june = population('june')
    after, later = population('later')
    for summary, label in ((june, 'June'), (later, 'October')):
        expected = receipt['population'][label]
        for field in ('candidates', 'authorizations', 'status_counts'):
            if summary[field] != expected[field]:
                raise ValueError(f'Independent reconstruction mismatch: {label} {field}')
    added, removed, shared = after.keys() - before.keys(), before.keys() - after.keys(), before.keys() & after.keys()
    transitions = Counter((before[k]['follow_up'], after[k]['follow_up']) for k in shared)
    changes = [{'product': k[0], 'tariff_record': k[1], 'policy': p,
                'before': before[k]['judgments'][p], 'after': after[k]['judgments'][p]}
               for k in sorted(shared) for p in POLICIES
               if before[k]['judgments'][p] != after[k]['judgments'][p]]
    expected = receipt['source_refresh_changes']
    if (added != {tuple(k) for k in expected['added_keys']} or
            removed != {tuple(k) for k in expected['removed_keys']} or
            sorted(changes, key=lambda r: (r['product'], r['tariff_record'], r['policy'])) !=
            sorted(expected['changed_shared_judgments'], key=lambda r: (r['product'], r['tariff_record'], r['policy']))):
        raise ValueError('Source refresh changes disagree with measured experiment')
    action_changed = {k for k in shared if before[k]['follow_up'] != after[k]['follow_up']}
    judgment_changed = {k for k in shared if before[k]['judgments'] != after[k]['judgments']}
    membership_changed = added | removed
    full_alerts = membership_changed | judgment_changed | action_changed
    stages = [('membership_only', membership_changed),
              ('membership_and_judgment', membership_changed | judgment_changed),
              ('membership_judgment_and_request', full_alerts)]
    ablation = []
    previous = set()
    for name, detected in stages:
        assert previous <= detected <= full_alerts
        ablation.append({'stage': name, 'detected_candidate_keys': len(detected),
                         'incremental_candidate_keys': len(detected - previous),
                         'omitted_full_workflow_keys': len(full_alerts - detected),
                         'detected_keys': [list(k) for k in sorted(detected)],
                         'incremental_keys': [list(k) for k in sorted(detected - previous)],
                         'omitted_keys': [list(k) for k in sorted(full_alerts - detected)]})
        previous = detected
    assert not (membership_changed & shared)
    alerts = []
    for key in sorted(added | removed | judgment_changed | action_changed):
        alerts.append({'product': key[0], 'tariff_record': key[1],
                       'change': 'added' if key in added else 'removed' if key in removed else 'reassessed',
                       'before': before.get(key), 'after': after.get(key)})
    report = {'analysis_type': 'exploratory documentary follow-up census',
              'action_precedence': ['no linked package', 'recorded finer conflict', 'missing exact route',
                                    'missing formulation', 'supported under both finer criteria'],
              'scope': 'Review categories are not clinical correctness or reimbursement eligibility judgments.',
              'source_states': {'june': june, 'later': later},
              'shared_action_transitions': [{'before': a, 'after': b, 'candidates': n}
                                           for (a, b), n in sorted(transitions.items())],
              'added': len(added), 'removed': len(removed), 'shared': len(shared),
              'changed_judgments': len(changes),
              'changed_shared_actions': len(action_changed),
              'action_changes_without_judgment_change': len(action_changed - judgment_changed),
              'monitoring_ablation': {'design': 'Retrospective component ablation on fixed sources, candidate keys and interpretation rules; no clinical recall reference standard.',
                                      'union_candidate_population': len(before.keys() | after.keys()),
                                      'changed_shared_judgment_keys': len(judgment_changed),
                                      'judgment_request_overlap': len(judgment_changed & action_changed),
                                      'stages': ablation},
              'alerts': alerts,
              'independent_receipt_agreement': True}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'practical_analysis.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    with (output / 'candidate_follow_up.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['snapshot', 'product', 'tariff', 'ATC', *POLICIES, 'follow_up', 'tariff_record', 'package_records'])
        for state, rows in [('june', before), ('later', after)]:
            for key, c in sorted(rows.items()):
                writer.writerow([state, key[0], c['tariff'], c['ATC'],
                                 *[c['judgments'][p] for p in POLICIES], c['follow_up'], key[1],
                                 ';'.join(p['record'] for p in c['packages'])])
    print(json.dumps({k: v for k, v in report.items() if k != 'alerts'}, indent=2))
    print(f'Saved {len(before) + len(after)} candidate rows and {len(alerts)} source-bound alerts to {output}.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.runs/practical')
    main(parser.parse_args().output)
