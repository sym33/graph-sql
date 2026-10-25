"""Census audit and claim-preserving extension of a fixed MediGraph snapshot.

All outcomes are structural/lexical. Empty human audit labels are intentional.
The implementation uses only Python's standard library.
"""
import argparse
import csv
import hashlib
import html
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from run_baseline import fingerprint, query

DELIMITERS = {'sai_praeparate.csv': ',', 'technisches_begleitblatt.csv': ',', 'atc_alterations.csv': ';', 'geloeschte_substanzen.csv': ';'}
CONTEXT = {
    'ema_products.csv': ('EMA', 'EU'), 'sai_praeparate.csv': ('Refdata_SAI', 'CH'),
    'sl.csv': ('BAG_specialty_list', 'CH'), 'gBA_icd.csv': ('GBA_ICD', 'DE'),
    'gBA_nutzenbewertung.csv': ('GBA_benefit_assessment', 'DE'),
    'atc_list.csv': ('WHO_ATC', 'international'), 'atc_ddd.csv': ('WHO_ATC_DDD', 'international'),
    'atc_alterations.csv': ('curated_ATC_alterations', 'international'),
}


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def valid(value):
    return bool(value and value.strip() and value.strip() != 'NA')


def read_inputs(root):
    files, records = {}, {}
    for path in sorted((root / 'input/silver').glob('*.csv')):
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f, delimiter=DELIMITERS.get(path.name, '|'), escapechar='\\'))
        assert all(None not in row and all(value is not None for value in row.values()) for row in rows), path.name
        files[path.name] = rows
        source, jurisdiction = CONTEXT.get(path.name, ('SwissDRG_or_curated_support', 'CH'))
        for ordinal, row in enumerate(rows, 1):
            rid = f'{path.name}:{file_hash}:record:{ordinal}'
            row['_record_id'] = rid
            records[rid] = {
                'id': rid, 'file': path.name, 'file_sha256': file_hash,
                'record_ordinal': ordinal, 'record_sha256': digest({k: v for k, v in row.items() if not k.startswith('_')}),
                'source': source, 'jurisdiction': jurisdiction,
                'validity_status': 'not_recoverable_from_staged_snapshot',
                'payload_json': json.dumps({k: v for k, v in row.items() if not k.startswith('_')}, ensure_ascii=False, sort_keys=True),
            }
            if path.name == 'ze_definitions.csv':
                records[rid]['tariff_atc'] = row['code']
    return files, records


def multiplicity(rows, key, values):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    result = []
    for name, items in groups.items():
        sets = {field: sorted({row[field] for row in items if valid(row[field])}) for field in values}
        if any(len(x) > 1 for x in sets.values()):
            result.append({'key': name, 'rows': len(items), 'values': sets, 'record_ids': [row['_record_id'] for row in items]})
    return sorted(result, key=lambda x: x['key'])


def build_layer(files, records, reverse=False):
    layer = {'records': records, 'products': {}, 'associations': {}, 'indications': {}}
    atc_index = {row['atc_code'] for row in files['atc_list.csv']}
    dictionary_hashes = sorted({r['file_sha256'] for r in records.values() if r.get('file')=='atc_list.csv'})
    code_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    sl_by_auth = defaultdict(list)
    history = defaultdict(list)
    for row in files['sl.csv']:
        if valid(row['zulassungsnummer']):
            sl_by_auth[row['zulassungsnummer']].append(row)
    for row in files['atc_alterations.csv']:
        history[row['ATC code']].append(row)

    def associate(subject, code, rule, premise_ids, context, status='source_association', extra=None):
        if not valid(code):
            return
        premise_ids = sorted(set(premise_ids))
        item = {'subject': subject, 'atc': code, 'rule': rule, 'premise_ids': premise_ids,
                'jurisdiction': context, 'evidence_status': status,
                'atc_in_snapshot': code in atc_index,
                'atc_index_snapshot_sha256': dictionary_hashes[0] if dictionary_hashes else 'fixture',
                'implementation_sha256': code_sha256,
                'validity_status': 'unknown_product_specific_validity'}
        item.update(extra or {})
        item['id'] = digest(item)
        layer['associations'][item['id']] = item

    def indication(subject, term, kind, premise, jurisdiction):
        if not valid(term):
            return
        item = {'subject': subject, 'term': term, 'kind': kind, 'record_id': premise, 'jurisdiction': jurisdiction}
        item['id'] = digest(item)
        layer['indications'][item['id']] = item

    for filename, source in [('sai_praeparate.csv', 'SAI'), ('ema_products.csv', 'EMA')]:
        for row in (reversed(files[filename]) if reverse else files[filename]):
            if source == 'SAI':
                subject = 'CH:authorization:' + row['ZULASSUNGSNUMMER']
                name, code, jurisdiction = row['Praep_Name'], row['ATC_CODE'], 'CH'
                product = {'id': subject, 'scope': 'Swiss_authorization', 'identity_rule': 'authorization_number'}
            else:
                subject = 'EMA:medicine:' + (row['url'] if valid(row['url']) else row['product_name'])
                name, code, jurisdiction = row['product_name'].lower(), row['atc'], 'EU'
                product = {'id': subject, 'scope': 'EMA_medicine', 'identity_rule': 'EMA_URL_or_source_name'}
            # Store the identifier scope, never overwrite names/ATC/indication values.
            layer['products'][subject] = product
            rid = row['_record_id']
            associate(subject, code, 'direct_' + source, [rid], jurisdiction)
            if source == 'SAI':
                for sl in sl_by_auth[row['ZULASSUNGSNUMMER']]:
                    associate(subject, sl['atc'], 'via_authorization_SL', [rid, sl['_record_id']], 'CH')
                for term in row['ANWENDUNGSGEBIET'].split(';'):
                    indication(subject, term.lower(), 'SAI_application_text', rid, 'CH')
            else:
                for term in row['mesh'].split(';'):
                    indication(subject, term.lower(), 'EMA_therapeutic_area_MeSH', rid, 'EU')
                indication(subject, row['indication'], 'EMA_therapeutic_indication_text', rid, 'EU')
            for alteration in history[code]:
                associate(subject, alteration['New ATC code'], 'historical_candidate', [rid, alteration['_record_id']], jurisdiction,
                          'context_review_required' if code in atc_index and alteration['New ATC code'] in atc_index else 'historical_mapping_candidate',
                          {'origin_atc': code, 'alteration_year': alteration['Year changed']})
    for row in (reversed(files['gBA_icd.csv']) if reverse else files['gBA_icd.csv']):
        subject = 'DE:GBA:trade_name:' + row['NAME_HN'].lower()
        layer['products'][subject] = {'id': subject, 'scope': 'GBA_trade_name_reference', 'identity_rule': 'source_scoped_trade_name_not_product_equivalence'}
        item = {'subject': subject, 'term': row['NAME_ICD_GROUPED'], 'kind': 'GBA_grouped_ICD_context',
                'icd': row['ID_ICD_GROUPED'], 'original_icd': row['ID_ICD'],
                'original_term': row['NAME_ICD'], 'record_id': row['_record_id'], 'jurisdiction': 'DE'}
        item['id'] = digest(item)
        layer['indications'][item['id']] = item
    return layer


def export_layer(root, layer):
    for kind in ['records', 'products', 'associations', 'indications']:
        with (root / 'results' / ('evidence_' + kind + '.jsonl')).open('w') as f:
            for key in sorted(layer[kind]):
                f.write(json.dumps(layer[kind][key], ensure_ascii=False, sort_keys=True) + '\n')


def ablations(layer):
    def pairs(items):
        return {(a['subject'], a['atc']) for a in items}
    all_items = list(layer['associations'].values())
    full = pairs(all_items)
    result = {}
    for mode, removed in [('no_SL', {'via_authorization_SL'}), ('no_history', {'historical_candidate'}), ('direct_only', {'via_authorization_SL', 'historical_candidate'}), ('no_SAI_direct', {'direct_SAI'}), ('no_EMA_direct', {'direct_EMA'})]:
        retained = pairs(a for a in all_items if a['rule'] not in removed)
        result[mode] = {'pairs_retained': len(retained), 'pairs_lost': len(full - retained)}
    source_removal = {}
    for source_file in ['sai_praeparate.csv','ema_products.csv','sl.csv','atc_alterations.csv']:
        retained = pairs(a for a in all_items if all(layer['records'][p]['file'] != source_file for p in a['premise_ids']))
        source_removal[source_file] = {'pairs_retained':len(retained),'pairs_lost':len(full-retained)}
    return {'full_distinct_product_code_pairs': len(full), 'rules': dict(Counter(a['rule'] for a in all_items)), 'ablations': result, 'source_removal':source_removal}


def compare_reports(root):
    reports = {}
    variants = ['original', 'reverse', 'repeat', 'replicate', 'shuffle_1', 'shuffle_2', 'shuffle_3']
    for variant in variants:
        path = root / 'results' / ('baseline_' + variant + '.json')
        if path.exists():
            reports[variant] = json.loads(path.read_text())
    result = {}
    for variant in variants[1:]:
        if variant not in reports or 'original' not in reports:
            continue
        a, b = reports['original']['snapshot'], reports[variant]['snapshot']
        result[variant] = {}
        for kind in ['product_properties', 'product_atc', 'indication_links', 'sl_links', 'all_nodes', 'all_edges']:
            sa = {json.dumps(row, sort_keys=True, ensure_ascii=False) for row in a[kind]}
            sb = {json.dumps(row, sort_keys=True, ensure_ascii=False) for row in b[kind]}
            result[variant][kind] = {'original_records': len(a[kind]), 'variant_records': len(b[kind]), 'removed_logical_records': len(sa-sb), 'added_logical_records': len(sb-sa), 'fingerprint_equal': a['fingerprints'][kind] == b['fingerprints'][kind]}
            if kind == 'product_properties':
                pa, pb = {x['name']: x['properties'] for x in a[kind]}, {x['name']: x['properties'] for x in b[kind]}
                changes = [{'name': k, 'original': pa.get(k), 'variant': pb.get(k)} for k in sorted(pa.keys() | pb.keys()) if pa.get(k) != pb.get(k)]
                result[variant][kind]['changed_products'] = len(changes)
                (root / 'results' / ('order_changes_' + variant + '.json')).write_text(json.dumps(changes, ensure_ascii=False, indent=2))
    return result, reports


def lexical_audit(files, reports):
    broad, strict, rows = set(), set(), []
    # Explicit lexical criterion; no claim to regulatory/clinical ground truth.
    malignancy = re.compile(r'\bovar(?:ian|y)\b[^.;\n]{0,100}\b(?:cancer|carcinoma|neoplasm)\b|\b(?:cancer|carcinoma|neoplasm)\b[^.;\n]{0,100}\bovar(?:ian|y)\b', re.I)
    adjacency = re.compile(r'ovarian\s+(?:epithelial\s+)?(?:cancer|carcinoma)|(?:cancer|carcinoma)\s+of\s+the\s+ovar', re.I)
    adjacent_products = set()
    sensitivity = {window:set() for window in [0,40,80,100,120]}
    for row in files['ema_products.csv']:
        name = row['product_name'].lower()
        is_broad = 'ovar' in (row['mesh'] + ' ' + row['indication']).lower()
        normalized = html.unescape(row['indication'])
        is_strict = bool(malignancy.search(normalized))
        if adjacency.search(normalized):
            adjacent_products.add(name)
        for window in sensitivity:
            pattern = re.compile(r'\bovar(?:ian|y)\b[^.;\n]{0,'+str(window)+r'}\b(?:cancer|carcinoma|neoplasm)\b|\b(?:cancer|carcinoma|neoplasm)\b[^.;\n]{0,'+str(window)+r'}\bovar(?:ian|y)\b', re.I)
            if pattern.search(normalized):
                sensitivity[window].add(name)
        if is_broad:
            broad.add(name)
            if is_strict:
                strict.add(name)
            rows.append({'product': name, 'mesh': row['mesh'], 'indication': row['indication'], 'broad_match': is_broad, 'explicit_malignancy_text_match': is_strict, 'record_id': row['_record_id']})
    staging_all = set(broad)
    staging_all.update(row['Praep_Name'].lower() for row in files['sai_praeparate.csv'] if 'ovar' in row['ANWENDUNGSGEBIET'].lower())
    staging_all.update(row['NAME_HN'].lower() for row in files['gBA_icd.csv'] if 'ovar' in (row['NAME_ICD']+' '+row['NAME_ICD_GROUPED']).lower())
    graph = {row['product'].lower() for row in reports.get('original', {}).get('snapshot', {}).get('ovar_paths', [])}
    return {'ema_broad_products': len(broad), 'ema_explicit_malignancy_products_among_broad': len(strict), 'ema_broad_without_explicit_malignancy': sorted(broad-strict), 'ema_adjacent_phrase_products': len(adjacent_products), 'proximity_window_sensitivity':{window:len(products) for window,products in sensitivity.items()}, 'staging_all_products': len(staging_all), 'graph_products': len(graph), 'staging_not_graph': sorted(staging_all-graph), 'graph_not_staging': sorted(graph-staging_all), 'criterion_regex': malignancy.pattern, 'criterion_status':'exploratory_rule_refined_after_inspection_of_staged_indication_texts_not_clinical_gold_standard', 'rows': rows}


def baseline_projection_audit(files, reports):
    report = reports.get('original')
    if not report or not report['completed']:
        return {}
    snapshot = report['snapshot']
    products = snapshot['product_properties']
    represented = {
        (p['properties'].get('Zulassungsnummer'), p['properties'].get('ATC-SAI'), p['properties'].get('Anwendungsgebiet'))
        for p in products if p['properties'].get('Zulassungsnummer') is not None
    }
    expected = {(r['ZULASSUNGSNUMMER'], r['ATC_CODE'], r['ANWENDUNGSGEBIET']) for r in files['sai_praeparate.csv']}
    missing = sorted(expected-represented)
    known_names = {p['name'] for p in products}
    expected_gba = {(r['NAME_HN'].lower(), r['NAME_ICD_GROUPED'], r['ID_ICD_GROUPED']) for r in files['gBA_icd.csv'] if r['NAME_HN'].lower() in known_names}
    actual_gba = {(r['product'],r['indication'],r['icd']) for r in snapshot['indication_links'] if r['source']=='gBA'}
    absent_gba = sorted(expected_gba-actual_gba)
    added_gba = sorted(actual_gba-expected_gba)
    return {'SAI_distinct_input_authorization_ATC_application_tuples':len(expected),
            'SAI_tuples_represented_in_any_product_node':len(expected & represented),
            'SAI_input_tuples_absent_from_product_properties':len(missing),
            'SAI_absent_examples':missing[:15],
            'GBA_expected_distinct_name_label_code_links_for_present_products':len(expected_gba),
            'GBA_realized_name_label_code_links':len(actual_gba),
            'GBA_expected_links_absent':len(absent_gba),
            'GBA_realized_links_not_in_expected_name_label_code_set':len(added_gba),
            'GBA_absent_examples':absent_gba[:15], 'GBA_added_examples':added_gba[:15]}


def load_layer(root, layer, run_label):
    # Baseline snapshots are saved before this separate model is loaded.
    query('MATCH (n) DETACH DELETE n')
    for item in query('SHOW CONSTRAINTS YIELD name RETURN name'):
        query('DROP CONSTRAINT `' + item['name'] + '`')
    for label in ['SourceRecord', 'ProductRef', 'Association', 'IndicationAssertion', 'SourceSnapshot', 'Rule', 'ATCConcept']:
        query(f'CREATE CONSTRAINT {label}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE')
    log = []

    def batches(kind, statement, transform=lambda x: x):
        rows = [transform(layer[kind][key]) for key in sorted(layer[kind], reverse=run_label=='reverse')]
        for offset in range(0, len(rows), 500):
            query(statement, {'rows': rows[offset:offset+500]})
        log.append({'kind': kind, 'rows': len(rows), 'statement': statement})

    batches('records', 'UNWIND $rows AS row MERGE (n:SourceRecord {id: row.id}) SET n += row MERGE (f:SourceSnapshot {id: row.file_sha256}) SET f.file = row.file MERGE (n)-[:IN_SNAPSHOT]->(f)')
    batches('products', 'UNWIND $rows AS row MERGE (n:ProductRef {id: row.id}) SET n += row')
    batches('associations', '''UNWIND $rows AS row
        MERGE (n:Association {id: row.id}) SET n += row
        WITH n, row
        MATCH (p:ProductRef {id: row.subject})
        MERGE (n)-[:ABOUT_PRODUCT]->(p)
        MERGE (a:ATCConcept {id: row.atc}) SET a.in_atc_snapshot = row.atc_in_snapshot
        MERGE (n)-[:TARGET_ATC]->(a)
        MERGE (r:Rule {id: row.rule + ':' + row.implementation_sha256})
        SET r.name = row.rule, r.implementation_sha256 = row.implementation_sha256
        MERGE (n)-[:GENERATED_BY]->(r)
        WITH n, row
        MATCH (d:SourceSnapshot {id: row.atc_index_snapshot_sha256})
        MERGE (n)-[:CHECKED_AGAINST]->(d)
        WITH n, row UNWIND row.premise_ids AS premise
        MATCH (s:SourceRecord {id: premise}) MERGE (n)-[:SUPPORTED_BY]->(s)''')
    batches('indications', '''UNWIND $rows AS row
        MERGE (n:IndicationAssertion {id: row.id}) SET n += row
        WITH n, row
        MATCH (p:ProductRef {id: row.subject}), (s:SourceRecord {id: row.record_id})
        MERGE (n)-[:ABOUT_PRODUCT]->(p) MERGE (n)-[:SUPPORTED_BY]->(s)''')
    checks = {
        'counts': 'MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS n ORDER BY label',
        'relationships': 'MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n ORDER BY type',
        'lineage': '''MATCH (a:Association) OPTIONAL MATCH (a)-[:SUPPORTED_BY]->(r:SourceRecord)-[:IN_SNAPSHOT]->(f:SourceSnapshot)
            WITH a, count(DISTINCT r) AS premises
            RETURN count(*) AS associations, sum(CASE WHEN premises = size(a.premise_ids) AND premises > 0 THEN 1 ELSE 0 END) AS complete_staged_lineage''',
        'rules': 'MATCH (a:Association) RETURN a.rule AS rule, count(*) AS n ORDER BY rule',
        'logical_associations': 'MATCH (a:Association) RETURN properties(a) AS properties',
        'logical_records': 'MATCH (r:SourceRecord) RETURN properties(r) AS properties',
        'logical_indications': 'MATCH (r:IndicationAssertion) RETURN properties(r) AS properties',
        'logical_products': 'MATCH (r:ProductRef) RETURN properties(r) AS properties',
        'reimbursement_paths': '''MATCH (a:Association)-[:TARGET_ATC]->(c:ATCConcept), (z:SourceRecord {file: 'ze_definitions.csv'})
            WHERE z.tariff_atc = c.id
            RETURN count(DISTINCT z) AS ze_records, count(DISTINCT a.subject) AS product_references, count(*) AS association_tariff_witnesses''',
        'examples': '''MATCH (a:Association)-[:SUPPORTED_BY]->(r:SourceRecord)
            WHERE a.atc IN ['L01BA01', 'L04AX03']
            RETURN a.id AS association, a.subject AS product, a.atc AS atc, a.rule AS rule, a.evidence_status AS status, collect(r.id) AS premises ORDER BY product, atc LIMIT 30''',
    }
    result = {key: query(stmt) for key, stmt in checks.items()}
    observed_counts = {item['label']:item['n'] for item in result['counts']}
    assert observed_counts['SourceRecord'] == len(layer['records'])
    assert observed_counts['Association'] == len(layer['associations'])
    assert observed_counts['IndicationAssertion'] == len(layer['indications'])
    assert result['lineage'][0]['complete_staged_lineage'] == len(layer['associations'])
    for kind, result_key in [('records','logical_records'),('associations','logical_associations'),('products','logical_products'),('indications','logical_indications')]:
        assert fingerprint([{'properties':value} for value in layer[kind].values()]) == fingerprint(result[result_key]), kind
    result['fingerprints'] = {key: fingerprint(value) for key, value in result.items() if isinstance(value, list)}
    result['queries'], result['load_queries'] = checks, log
    (root/'results'/('evidence_graph_'+run_label+'.json')).write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return {'counts': result['counts'], 'lineage': result['lineage'], 'fingerprints': result['fingerprints'], 'reimbursement_paths': result['reimbursement_paths']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--load-graph', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    files, records = read_inputs(root)
    layer = build_layer(files, records)
    reverse = build_layer(files, records, reverse=True)
    assert layer == reverse, 'Evidence model must be independent of iteration order'
    # Premise closure and content hashes are executable invariants.
    for association in layer['associations'].values():
        assert association['premise_ids'] and all(p in records for p in association['premise_ids'])
        assert association['subject'] in layer['products']
    export_layer(root, layer)
    comparison, reports = compare_reports(root)
    sai_ambiguity = multiplicity(files['sai_praeparate.csv'], 'Praep_Name', ['ZULASSUNGSNUMMER', 'ATC_CODE', 'ANWENDUNGSGEBIET'])
    gba_ambiguity = multiplicity(files['gBA_icd.csv'], 'NAME_ICD_GROUPED', ['ID_ICD_GROUPED'])
    sl_ambiguity = multiplicity(files['sl.csv'], 'bezeichnung', ['gtin', 'zulassungsnummer', 'atc'])
    (root/'results/input_ambiguities.json').write_text(json.dumps({'SAI': sai_ambiguity, 'GBA': gba_ambiguity, 'SL': sl_ambiguity}, ensure_ascii=False, indent=2))
    sl_by_auth = defaultdict(set)
    for row in files['sl.csv']:
        if valid(row['atc']):
            sl_by_auth[row['zulassungsnummer']].add(row['atc'])
    discordance = []
    for row in files['sai_praeparate.csv']:
        codes = sl_by_auth[row['ZULASSUNGSNUMMER']]
        if codes and any(code != row['ATC_CODE'] for code in codes):
            discordance.append({'name': row['PRAEPARATENAME'], 'authorization': row['ZULASSUNGSNUMMER'], 'SAI_ATC': row['ATC_CODE'], 'SL_ATC': sorted(codes), 'record_id': row['_record_id']})
    (root/'results/authorization_code_discordance.json').write_text(json.dumps(discordance, ensure_ascii=False, indent=2))
    lexical = lexical_audit(files, reports)
    (root/'results/lexical_ovar_audit.json').write_text(json.dumps(lexical, ensure_ascii=False, indent=2))
    # Deterministic pilot queue: up to 50 cases per available rule stratum.
    rng = random.Random(20261009)
    audit_rows = []
    for rule in sorted({a['rule'] for a in layer['associations'].values()}):
        candidates = sorted([a for a in layer['associations'].values() if a['rule']==rule], key=lambda a:a['id'])
        for a in rng.sample(candidates, min(50, len(candidates))):
            audit_rows.append({'association_id': a['id'], 'stratum': rule, 'product_reference': a['subject'], 'atc': a['atc'], 'premise_ids': json.dumps(a['premise_ids']), 'reviewer_1': '', 'reviewer_2': '', 'adjudicated_label': '', 'error_mode': '', 'notes': ''})
    unresolved = sorted([a for a in layer['associations'].values() if not a['atc_in_snapshot'] and a['rule'].startswith('direct_')], key=lambda a:a['id'])
    for a in rng.sample(unresolved, min(50, len(unresolved))):
        audit_rows.append({'association_id':a['id'], 'stratum':'unresolved_ATC', 'product_reference':a['subject'], 'atc':a['atc'], 'premise_ids':json.dumps(a['premise_ids']), 'reviewer_1':'', 'reviewer_2':'', 'adjudicated_label':'', 'error_mode':'', 'notes':''})
    with (root/'results/expert_audit_queue.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(audit_rows[0]))
        writer.writeheader(); writer.writerows(audit_rows)
    summary = {
        'source_records': len(records), 'source_files': len(files),
        'SAI_rows': len(files['sai_praeparate.csv']), 'SAI_short_names': len({r['Praep_Name'] for r in files['sai_praeparate.csv']}),
        'SAI_short_names_multiple_authorizations': sum(len(x['values']['ZULASSUNGSNUMMER'])>1 for x in sai_ambiguity),
        'SAI_short_names_multiple_ATC': sum(len(x['values']['ATC_CODE'])>1 for x in sai_ambiguity),
        'SAI_short_names_multiple_application_texts': sum(len(x['values']['ANWENDUNGSGEBIET'])>1 for x in sai_ambiguity),
        'SAI_rows_in_multiple_authorization_groups': sum(x['rows'] for x in sai_ambiguity if len(x['values']['ZULASSUNGSNUMMER'])>1),
        'GBA_grouped_labels_multiple_codes': len(gba_ambiguity), 'SL_names_multiple_values': len(sl_ambiguity),
        'SAI_rows_with_SL_matches': sum(bool(sl_by_auth[r['ZULASSUNGSNUMMER']]) for r in files['sai_praeparate.csv']),
        'SAI_rows_with_discordant_SL_code': len(discordance),
        'evidence_product_references': len(layer['products']), 'evidence_associations': len(layer['associations']),
        'evidence_indication_assertions': len(layer['indications']),
        'historical_candidate_status': dict(Counter(a['evidence_status'] for a in layer['associations'].values() if a['rule']=='historical_candidate')),
        'extension_iteration_invariant': layer == reverse,
        'ablation': ablations(layer), 'baseline_comparisons': comparison,
        'baseline_projection_audit': baseline_projection_audit(files, reports),
        'baseline_builds': {k: {'completed': v['completed'], 'statements': v['statements_executed'], 'seconds': v['elapsed_seconds'], 'nodes': v['snapshot']['nodes'][0]['n'], 'relationships': v['snapshot']['relationships'][0]['n'], 'graph_ovar_products':len({r['product'] for r in v['snapshot']['ovar_paths']})} for k,v in reports.items()},
        'lexical_search': {k:v for k,v in lexical.items() if k!='rows'},
        'expert_audit_cases': len(audit_rows), 'expert_audit_completed': False,
    }
    if args.load_graph:
        summary['extension_graph_original'] = load_layer(root, layer, 'original')
        summary['extension_graph_reverse'] = load_layer(root, reverse, 'reverse')
        summary['extension_loaded_order_invariant'] = all(summary['extension_graph_original']['fingerprints'][k] == summary['extension_graph_reverse']['fingerprints'][k] for k in ['logical_associations', 'logical_records', 'logical_indications', 'logical_products'])
    elif (root/'results/evidence_graph_original.json').exists() and (root/'results/evidence_graph_reverse.json').exists():
        for name in ['original', 'reverse']:
            result = json.loads((root/'results'/('evidence_graph_'+name+'.json')).read_text())
            summary['extension_graph_'+name] = {key:result[key] for key in ['counts', 'lineage', 'fingerprints', 'reimbursement_paths']}
        summary['extension_loaded_order_invariant'] = all(summary['extension_graph_original']['fingerprints'][k] == summary['extension_graph_reverse']['fingerprints'][k] for k in ['logical_associations', 'logical_records', 'logical_indications', 'logical_products'])
    (root/'results/empirical_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
