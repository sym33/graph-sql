"""Census perturbations and priority sensitivity on frozen documentary records.

The cache test uses an offline graph reference and SQLite reconstruction. It
complements, and does not replace, the retained native Neo4j refresh experiments.
"""
from pathlib import Path
from collections import Counter, defaultdict
from itertools import permutations
import argparse
import copy
import hashlib
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from example import load, aggregate, follow_up
from practical_analysis import population, POLICIES


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Model:
    def __init__(self, snapshot):
        db, records, self.assess = load(snapshot)
        db.close()
        self.rows = {}
        self.index = defaultdict(lambda: defaultdict(set))
        self.tariffs = defaultdict(set)
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE source(id TEXT PRIMARY KEY,kind TEXT,auth TEXT,code TEXT)')
        self.db.execute('CREATE INDEX source_auth ON source(kind,auth)')
        self.db.execute('CREATE INDEX source_code ON source(kind,code)')
        for name, values in records.items():
            if name == '_WHO':
                continue
            for rid, r in values:
                if name == 'sai_praeparate.csv':
                    row = dict(id=rid, kind='sai', auth=r['ZULASSUNGSNUMMER'], code=r['ATC_CODE'])
                elif name == 'sl.csv':
                    row = dict(id=rid, kind='sl', auth=r['zulassungsnummer'], code=r['atc'],
                               group=r['gammenbezeichnung'], package=r['bezeichnung'])
                else:
                    row = dict(id=rid, kind='tariff', auth='', code=r['code'], route=r['va'])
                    self.tariffs[row['code']].add(rid)
                self.set(rid, row)

    def set(self, rid, row):
        previous = self.rows.pop(rid, None)
        if previous:
            self.index[previous['auth']][previous['kind']].discard(rid)
            self.db.execute('DELETE FROM source WHERE id=?', (rid,))
        if row is not None:
            self.rows[rid] = row
            self.index[row['auth']][row['kind']].add(rid)
            self.db.execute('INSERT INTO source VALUES(?,?,?,?)',
                            (rid, row['kind'], row['auth'], row['code']))

    def assemble(self, paths):
        groups = defaultdict(set)
        for auth, tariff, kind, sai, package in paths:
            groups[(auth, tariff)].add((kind, sai, package))
        answers = {}
        for (auth, tariff), premises in groups.items():
            package_ids = sorted({p for _, _, p in premises if p})
            packages = [self.rows[p] for p in package_ids]
            judgments = {policy: aggregate([self.assess(p['group'], p['package'],
                         self.rows[tariff]['route'], policy) for p in packages]) for policy in POLICIES}
            answers[(auth, tariff)] = {'paths': sorted(premises), 'packages': packages,
                                      'judgments': judgments,
                                      'request': follow_up({'packages': packages, 'judgments': judgments})}
        return answers

    def sql(self, auths, guarded=True):
        auths = sorted(auths)
        if not auths:
            return {}
        placeholders = ','.join('?' for _ in auths)
        guard = "AND trim(s.auth) NOT IN ('','NA')" if guarded else ''
        common = f"s.kind='sai' AND s.auth IN ({placeholders}) {guard}"
        direct = f'''SELECT s.auth,t.id,'direct',s.id,'' FROM source s
                     JOIN source t ON t.kind='tariff' AND t.code=s.code
                     WHERE {common} AND trim(s.code) NOT IN ('','NA')'''
        linked = f'''SELECT s.auth,t.id,'SL',s.id,p.id FROM source s
                     JOIN source p ON p.kind='sl' AND p.auth=s.auth
                     JOIN source t ON t.kind='tariff' AND t.code=p.code
                     WHERE {common} AND trim(p.code) NOT IN ('','NA')'''
        return self.assemble(self.db.execute(direct+' UNION '+linked, auths+auths).fetchall())

    def graph(self, auths):
        paths = set()
        for auth in auths:
            if str(auth).strip() in ('', 'NA'):
                continue
            for sid in self.index[auth]['sai']:
                sai = self.rows[sid]
                if sai['code'].strip() not in ('', 'NA'):
                    for tid in self.tariffs.get(sai['code'], ()):
                        paths.add((auth, tid, 'direct', sid, ''))
                for pid in self.index[auth]['sl']:
                    package = self.rows[pid]
                    if package['code'].strip() not in ('', 'NA'):
                        for tid in self.tariffs.get(package['code'], ()):
                            paths.add((auth, tid, 'SL', sid, pid))
        return self.assemble(paths)


def applicable(candidate):
    j = candidate['judgments']
    return {'conflict': 'CONTRADICTED' in (j['exact_code'], j['explicit_formulation']),
            'route': j['exact_code'] == 'UNDETERMINED',
            'formulation': j['explicit_formulation'] == 'UNDETERMINED'}


def request(candidate, order):
    if not candidate['packages']:
        return 'obtain_linked_package_evidence'
    labels = {'conflict': 'review_route_or_formulation_conflict',
              'route': 'obtain_explicit_route', 'formulation': 'obtain_formulation_evidence'}
    rules = applicable(candidate)
    return next((labels[r] for r in order if rules[r]), 'retain_supported_context')


def main(output):
    protocol_path = Path(__file__).with_name('protocol.json')
    protocol = json.loads(protocol_path.read_text())
    populations = {state: population(state)[0] for state in protocol['source_states']}
    shared = populations['june'].keys() & populations['later'].keys()
    default_changes = {k for k in shared if populations['june'][k]['follow_up'] != populations['later'][k]['follow_up']}
    priority = []
    for order in permutations(('conflict', 'route', 'formulation')):
        differences = {state: sum(request(c, order) != c['follow_up'] for c in rows.values())
                       for state, rows in populations.items()}
        changes = {k for k in shared if request(populations['june'][k], order) !=
                                      request(populations['later'][k], order)}
        priority.append({'order': list(order), 'route_before_formulation': order.index('route') < order.index('formulation'),
                         'changed_requests_against_default': differences,
                         'shared_update_request_changes': len(changes),
                         'changed_update_keys_against_default': len(changes ^ default_changes),
                         'shared_change_keys': [list(k) for k in sorted(changes)]})
    by_state = {}
    for state, population_rows in populations.items():
        m = Model(state)
        auths = {k[0].removeprefix('CH:authorization:') for k in population_rows}
        baseline = m.graph(auths)
        assert baseline == m.sql(auths)
        for (auth, tariff), row in baseline.items():
            reference = population_rows[('CH:authorization:'+auth, tariff)]
            assert row['judgments'] == reference['judgments']
            assert row['request'] == reference['follow_up']
            assert {p['id'] for p in row['packages']} == {p['record'] for p in reference['packages']}
        eligible = sorted({p['id'] for r in baseline.values() for p in r['packages']})
        counters = defaultdict(Counter)
        audit = []
        for rid in eligible:
            original = dict(m.rows[rid])
            other = min(auths - {original['auth']})
            variants = {'missing_authorization': dict(original, auth=''),
                        'dangling_authorization': dict(original, auth='MISSING:'+rid),
                        'missing_classification': dict(original, code=''),
                        'unmatched_classification': dict(original, code='MISSING:'+rid),
                        'valid_identifier_reassignment': dict(original, auth=other),
                        'masked_route': dict(original, group='', package='')}
            for label, modified in variants.items():
                affected = {original['auth'], modified['auth']}
                old = {k:v for k,v in baseline.items() if k[0] in affected}
                try:
                    m.set(rid, modified)
                    graph, sql = m.graph(affected), m.sql(affected)
                    assert graph == sql
                    gained = graph.keys() - old.keys()
                    if label != 'valid_identifier_reassignment':
                        assert not gained
                    added_paths = sum(len(set(v['paths'])-set(old.get(k, {}).get('paths', ()))) for k,v in graph.items())
                    c = counters[label];c['trials'] += 1;c['changed_answers'] += graph != old
                    c['trials_with_added_candidates'] += bool(gained)
                    c['added_candidate_occurrences'] += len(gained)
                    c['trials_with_added_paths'] += bool(added_paths)
                    c['lost_candidate_occurrences'] += len(old.keys()-graph.keys())
                    common = old.keys() & graph.keys()
                    c['judgment_change_occurrences'] += sum(old[k]['judgments'] != graph[k]['judgments'] for k in common)
                    c['request_change_occurrences'] += sum(old[k]['request'] != graph[k]['request'] for k in common)
                    audit.append({'record':rid,'test':label,'changed':graph!=old,'added':len(gained),
                                  'lost':len(old.keys()-graph.keys()),'result_sha256':digest(sorted(graph.items()))})
                finally:
                    m.set(rid, original)
            # Deliberate stale-cache controls with graph-reference rebuild and SQL oracle.
            for label, modified in {'delete': None, 'change_code': dict(original, code='MISSING:'+rid),
                                    'change_route': dict(original, group='', package=''),
                                    'insert_copy': dict(original, id='INSERT:'+rid)}.items():
                target = 'INSERT:'+rid if label=='insert_copy' else rid
                affected = {original['auth']}
                old = {k:v for k,v in baseline.items() if k[0] in affected}
                try:
                    m.set(target, modified)
                    expected = m.sql(affected)
                    repaired = m.graph(affected)
                    assert repaired == expected == m.graph(affected)
                    # The stale control reuses the pre-edit answer and must be distinguishable.
                    stale = old != expected
                    assert stale
                    c=counters['update_'+label];c['trials']+=1;c['stale_controls_detected']+=stale
                    c['repaired_mismatches']+=repaired!=expected
                    c['candidate_key_changes']+=set(old)!=set(expected)
                    common = old.keys() & expected.keys()
                    c['judgment_change_occurrences'] += sum(old[k]['judgments'] != expected[k]['judgments'] for k in common)
                    c['request_change_occurrences'] += sum(old[k]['request'] != expected[k]['request'] for k in common)
                    audit.append({'record':rid,'test':'update_'+label,'stale':stale,
                                  'result_sha256':digest(sorted(repaired.items()))})
                finally:
                    m.set(target, None if label=='insert_copy' else original)
                assert m.graph(affected)==old
        # Co-missing identifiers: compare unrestricted equality with the admissibility guard.
        first = m.rows[eligible[0]]
        sa = {'id':'CONTROL:SAI','kind':'sai','auth':'','code':first['code']}
        sl = dict(first, id='CONTROL:SL', auth='')
        m.set(sa['id'],sa);m.set(sl['id'],sl)
        guarded, unguarded = m.sql({''}), m.sql({''}, guarded=False)
        assert guarded == m.graph({''}) == {} and unguarded
        m.set(sa['id'],None);m.set(sl['id'],None)
        assert m.graph(auths)==baseline==m.sql(auths)
        by_state[state]={'candidates':len(baseline),'eligible_package_records':len(eligible),
                         'tests':{k:dict(v) for k,v in sorted(counters.items())},
                         'co_missing_identifier_control':{'guarded_candidates':len(guarded),
                                                         'unguarded_candidates':len(unguarded)},
                         'trial_digest':digest(audit),'all_restorations_equal':True}
        output.mkdir(parents=True,exist_ok=True)
        (output/(state+'_trials.json')).write_text(json.dumps(audit,indent=2)+'\n')
        m.db.close()
    result={'design':protocol,'protocol_sha256':hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
            'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'priority_sensitivity':priority,'source_states':by_state,
            'scope':'Offline source perturbations and graph-reference cache checks; no new native Neo4j update or clinical validation claim.'}
    (output/'robustness.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'priority_sensitivity':[{k:v for k,v in x.items() if k!='shared_change_keys'} for x in priority],
                      'source_states':by_state},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'.runs/robustness')
    main(parser.parse_args().output)
