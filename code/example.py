"""Trace one medication–tariff question from the included source records.

Standard-library entry point. The source and route definitions are the ones
used by the complete experiments; no graph server or generated output is needed.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
SOURCES = 'Graph_Validation_V9/temporal_snapshot/input/silver'
POLICY = 'Graph_Validation_V17/code/route_policies.py'


def verified_bytes(relative, manifest):
    content = (ROOT / relative).read_bytes()
    expected = manifest.get(relative)
    if expected is None or hashlib.sha256(content).hexdigest() != expected:
        raise ValueError('Input integrity check failed: ' + relative)
    return content


def load(snapshot="june"):
    manifest = {r['path']: r['sha256'] for r in json.loads((ROOT / 'MANIFEST.json').read_text())['files']}
    verified_bytes(POLICY, manifest)
    sys.path.insert(0, str(ROOT / Path(POLICY).parent))
    from route_policies import assess
    records = {}
    for name, delimiter in [('sai_praeparate.csv', ','), ('sl.csv', '|'),
                            ('ze_definitions.csv', '|')]:
        relative = (('Source_Refresh/input/silver/' + name)
                    if snapshot == 'later' and name in ('sl.csv', 'sai_praeparate.csv')
                    else SOURCES + '/' + name)
        raw = verified_bytes(relative, manifest)
        digest = hashlib.sha256(raw).hexdigest()
        # newline-preserving CSV parsing matches the frozen source reference.
        import io
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''),
                                delimiter=delimiter, escapechar='\\')
        records[name] = [(f'{name}:{digest}:record:{n}', row)
                         for n, row in enumerate(reader, 1)]
    who_path = 'Thesis_Recovery/results/WHO_full_code_alterations.json'
    who_raw = verified_bytes(who_path, manifest)
    who_digest = hashlib.sha256(who_raw).hexdigest()
    records['_WHO'] = [(f'WHO_alterations:{who_digest}:record:{n}', row)
                       for n, row in enumerate(json.loads(who_raw), 1)]
    db = sqlite3.connect(':memory:')
    db.executescript('''
        CREATE TABLE sai(record TEXT, authorization TEXT, code TEXT);
        CREATE TABLE sl(record TEXT, authorization TEXT, code TEXT);
        CREATE TABLE tariff(record TEXT, code TEXT);
        CREATE INDEX sai_auth ON sai(authorization);
        CREATE INDEX sl_auth ON sl(authorization);
        CREATE INDEX tariff_code ON tariff(code);
    ''')
    db.executemany('INSERT INTO sai VALUES(?,?,?)',
                   [(k, r['ZULASSUNGSNUMMER'], r['ATC_CODE']) for k, r in records['sai_praeparate.csv']])
    db.executemany('INSERT INTO sl VALUES(?,?,?)',
                   [(k, r['zulassungsnummer'], r['atc']) for k, r in records['sl.csv']])
    db.executemany('INSERT INTO tariff VALUES(?,?)',
                   [(k, r['code']) for k, r in records['ze_definitions.csv']])
    return db, records, assess


def aggregate(values):
    if 'VERIFIED' in values:
        return 'VERIFIED'
    if values and all(v == 'CONTRADICTED' for v in values):
        return 'CONTRADICTED'
    return 'UNDETERMINED'



def follow_up(candidate):
    """Exclusive next evidence request; recorded finer conflicts take precedence."""
    judgments = candidate['judgments']
    if not candidate['packages']:
        return 'obtain_linked_package_evidence'
    if 'CONTRADICTED' in (judgments['exact_code'], judgments['explicit_formulation']):
        return 'review_route_or_formulation_conflict'
    if judgments['exact_code'] == 'UNDETERMINED':
        return 'obtain_explicit_route'
    if judgments['explicit_formulation'] == 'UNDETERMINED':
        return 'obtain_formulation_evidence'
    return 'retain_supported_context'


ACTIONS = {
    'obtain_linked_package_evidence': 'Obtain authorization-linked package evidence for this candidate.',
    'review_route_or_formulation_conflict': 'Review the route or formulation conflict; retain the classification connection separately.',
    'obtain_explicit_route': 'Obtain an explicit administration route for the linked packages.',
    'obtain_formulation_evidence': 'Obtain explicit formulation evidence for the linked packages.',
    'retain_supported_context': 'Retain the source-backed candidate and review applicable tariff and case conditions before operational use.'
}


def analyze(authorization, db, records, assess):
    product_rows = [(k, r) for k, r in records['sai_praeparate.csv']
                    if r['ZULASSUNGSNUMMER'] == authorization]
    if not product_rows:
        raise ValueError('Authorization not present in the included snapshot: ' + authorization)
    direct = {r[0] for r in db.execute('''
        SELECT DISTINCT t.record FROM sai s JOIN tariff t ON s.code=t.code
        WHERE s.authorization=? AND coalesce(trim(s.code),'') NOT IN ('','NA')
    ''', (authorization,))}
    linked = {r[0] for r in db.execute('''
        SELECT DISTINCT t.record FROM sai s JOIN sl l ON s.authorization=l.authorization
        JOIN tariff t ON l.code=t.code
        WHERE s.authorization=? AND coalesce(trim(l.code),'') NOT IN ('','NA')
    ''', (authorization,))}
    packages = [(k, r) for k, r in records['sl.csv'] if r['zulassungsnummer'] == authorization]
    sai_codes = sorted({r['ATC_CODE'] for _, r in product_rows})
    sl_codes = sorted({r['atc'] for _, r in packages})
    tariffs = dict(records['ze_definitions.csv'])
    candidates = []
    for tid in sorted(direct | linked):
        tariff = tariffs[tid]
        witnesses = []
        for rid, package in packages:
            if rid and tid in linked and package['atc'] == tariff['code']:
                judgments = {policy: assess(package['gammenbezeichnung'], package['bezeichnung'],
                                             tariff['va'], policy)
                             for policy in ('coarse', 'exact_code', 'explicit_formulation')}
                witnesses.append({'record': rid, 'package': package['bezeichnung'],
                                  'recorded_group': package['gammenbezeichnung'], 'judgments': judgments})
        judgments = {policy: aggregate([w['judgments'][policy] for w in witnesses])
                     for policy in ('coarse', 'exact_code', 'explicit_formulation')}
        histories = [{'old': r['old'], 'new': r['new'],
                      'year': r['year'], 'record': rid}
                     for rid, r in records['_WHO']
                     if r['old'] in sai_codes and r['new'] == tariff['code']]
        category = follow_up({'packages': witnesses, 'judgments': judgments})
        action = ACTIONS[category]
        candidates.append({'tariff': tariff['ze_code'], 'tariff_record': tid,
                           'catalogue_version': tariff['version'], 'ATC': tariff['code'],
                           'tariff_routes': tariff['va'], 'direct_lookup': tid in direct,
                           'linked_SL': tid in linked, 'judgments': judgments,
                           'classification_history': histories, 'packages': witnesses,
                           'follow_up': category, 'next_action': action})
    return {'authorization': authorization,
            'product': sorted({r['PRAEPARATENAME'] for _, r in product_rows}),
            'SAI_records': [k for k, _ in product_rows], 'SAI_codes': sai_codes, 'SL_codes': sl_codes,
            'direct_candidates': len(direct), 'source_complete_candidates': len(direct | linked),
            'additional_candidates': len(linked - direct), 'candidates': candidates}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization', default='67648', help='Swiss authorization identifier; default: Tabrecta 67648.')
    parser.add_argument('--snapshot', choices=('june', 'later'), default='june',
                        help='Frozen source state; the tariff remains fixed.')
    parser.add_argument('--json', action='store_true', help='Print source-bound structured output.')
    args = parser.parse_args()
    try:
        answer = analyze(args.authorization, *load(args.snapshot))
        answer['snapshot'] = args.snapshot
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')
    if args.json:
        print(json.dumps(answer, ensure_ascii=False, indent=2))
        return
    print('; '.join(answer['product']) + ' | authorization ' + answer['authorization'])
    print('SAI ATC: ' + ', '.join(answer['SAI_codes']) + ' | SL ATC: ' + ', '.join(answer['SL_codes']))
    print(f"Candidates: direct {answer['direct_candidates']}; source-complete {answer['source_complete_candidates']}; additional {answer['additional_candidates']}")
    labels = {'VERIFIED': 'compatible', 'CONTRADICTED': 'conflicting', 'UNDETERMINED': 'unresolved'}
    for c in answer['candidates']:
        print(f"{c['tariff']} ({c['catalogue_version']}) | ATC {c['ATC']} | tariff route {c['tariff_routes']}")
        print('  ' + '; '.join(f'{p}: {labels[v]}' for p, v in c['judgments'].items()))
        for h in c['classification_history']:
            print(f"  Recorded WHO alteration: {h['old']} -> {h['new']} ({h['year']})")
        print('  Next: ' + c['next_action'])
    if not answer['candidates']:
        print('No candidate under the included classification and catalogue records.')


if __name__ == '__main__':
    main()
