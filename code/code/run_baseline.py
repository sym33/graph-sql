"""Run frozen MediGraph loader in a dedicated local-only Neo4j instance.

No production database is supported: endpoint is fixed to the isolated research
port and this script clears only that experimental database between builds.
"""
import argparse
import csv
import hashlib
import json
import re
import random
import time
from pathlib import Path
from urllib.parse import unquote
from urllib.request import Request, urlopen

ENDPOINT = 'http://127.0.0.1:17474/db/neo4j/tx/commit'


def query(statement, parameters=None):
    body = json.dumps({'statements': [{'statement': statement, 'parameters': parameters or {}}]}).encode()
    with urlopen(Request(ENDPOINT, data=body, headers={'Content-Type': 'application/json'}), timeout=900) as response:
        result = json.load(response)
    if result['errors']:
        raise RuntimeError(json.dumps(result['errors'], ensure_ascii=False))
    r = result['results'][0]
    return [dict(zip(r['columns'], item['row'])) for item in r['data']]


def statements(text):
    # Cypher semicolons inside string literals are not statement separators.
    out, quote, comment, i = [], None, False, 0
    while i < len(text):
        char = text[i]
        if comment:
            if char == '\n':
                comment = False
                out.append(char)
        elif quote:
            out.append(char)
            if char == '\\' and i + 1 < len(text):
                i += 1
                out.append(text[i])
            elif char == quote:
                quote = None
        elif char in "'\"`":
            quote = char
            out.append(char)
        elif text[i:i+2] == '//':
            comment = True
            i += 1
        elif char == ';':
            statement = ''.join(out).strip()
            if statement:
                yield statement
            out = []
        else:
            out.append(char)
        i += 1
    statement = ''.join(out).strip()
    if statement:
        yield statement


def fingerprint(rows):
    canonical = sorted(json.dumps(x, sort_keys=True, ensure_ascii=False) for x in rows)
    return hashlib.sha256('\n'.join(canonical).encode()).hexdigest()


def snapshot():
    q = {
        'nodes': 'MATCH (n) RETURN count(n) AS n',
        'relationships': 'MATCH ()-[r]->() RETURN count(r) AS n',
        'labels': 'MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS n ORDER BY label',
        'types': 'MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n ORDER BY type',
        'product_properties': 'MATCH (p:Präparat) RETURN p.Name AS name, properties(p) AS properties ORDER BY name',
        'product_atc': 'MATCH (p:Präparat)-[r:HAT_ATC|HATTE_ATC]->(s:Substanz) RETURN p.Name AS product, type(r) AS type, s.Name AS atc, properties(r) AS properties ORDER BY product, type, atc',
        'indication_links': 'MATCH (p:Präparat)-[r:INDIZIERT_FUER]->(i:Indikation) RETURN p.Name AS product, i.Name AS indication, i.ICD AS icd, r.Quelle AS source ORDER BY product, indication, source',
        'sl_links': 'MATCH (p:Präparat)-[:IST_AUF_SL]->(s:Spezialitätenliste) RETURN p.Name AS product, s.Name AS package, s.Zulassungsnummer AS authorization ORDER BY product, package',
        'ovar_paths': "MATCH (i:Indikation)<-[r:INDIZIERT_FUER]-(p:Präparat) WHERE toLower(i.Name) CONTAINS 'ovar' RETURN DISTINCT p.Name AS product, i.Name AS indication, r.Quelle AS source ORDER BY product, indication",
        'ze_drilldown': 'MATCH (z:Zusatzentgelt)<-[:HAT_ZE]-(s:Substanz) OPTIONAL MATCH (p:Präparat)-[:HAT_ATC]->(s) RETURN z.Name AS ze, s.Name AS atc, count(DISTINCT p) AS products ORDER BY ze, atc',
        'provenance': 'MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS total, sum(CASE WHEN r.Quelle IS NOT NULL THEN 1 ELSE 0 END) AS with_source ORDER BY type',
        'all_nodes': 'MATCH (n) RETURN labels(n) AS labels, properties(n) AS properties',
        'all_edges': 'MATCH (a)-[r]->(b) RETURN labels(a) AS source_labels, properties(a) AS source_properties, type(r) AS type, properties(r) AS properties, labels(b) AS target_labels, properties(b) AS target_properties',
    }
    data = {name: query(statement) for name, statement in q.items()}
    data['queries'] = q
    data['fingerprints'] = {k: fingerprint(v) for k, v in data.items() if isinstance(v, list)}
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--variant', choices=['original', 'reverse', 'repeat', 'shuffle', 'replicate'], default='original')
    parser.add_argument('--seed', type=int, default=1)
    args = parser.parse_args()
    tag = 'shuffle_' + str(args.seed) if args.variant == 'shuffle' else args.variant
    rng = random.Random(args.seed)
    root = args.root.resolve()
    out = root / 'results'
    out.mkdir(exist_ok=True)
    neo_import = root / 'software/neo4j-community-5.26.1/import'
    neo_import.mkdir(exist_ok=True)
    for source in (root / 'input/silver').glob('*.csv'):
        content = source.read_bytes()
        if args.variant in ['reverse', 'shuffle']:
            delimiter = {'sai_praeparate.csv': ',', 'technisches_begleitblatt.csv': ',', 'atc_alterations.csv': ';', 'geloeschte_substanzen.csv': ';'}.get(source.name, '|')
            with source.open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.reader(f, delimiter=delimiter, escapechar='\\'))
            with (neo_import / source.name).open('w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, delimiter=delimiter, escapechar='\\', doublequote=False, quoting=csv.QUOTE_ALL)
                writer.writerow(rows[0])
                transformed = list(reversed(rows[1:])) if args.variant == 'reverse' else list(rows[1:])
                if args.variant == 'shuffle':
                    rng.shuffle(transformed)
                writer.writerows(transformed)
            with (neo_import / source.name).open(encoding='utf-8', newline='') as f:
                roundtrip = list(csv.reader(f, delimiter=delimiter, escapechar='\\'))
            assert roundtrip == [rows[0]] + transformed, source.name
            assert sorted(rows[1:]) == sorted(transformed), source.name
        else:
            (neo_import / source.name).write_bytes(content)
    loader = (root / 'input/loader.cypher').read_text()
    loader = re.sub(r'https://raw\.githubusercontent\.com/[^\s\'\"]+', lambda m: 'file:///' + unquote(m.group(0).split('/')[-1]), loader)
    (out / ('loader_' + tag + '.cypher')).write_text(loader)
    if args.variant != 'repeat':
        query('MATCH (n) DETACH DELETE n')
        for item in query('SHOW CONSTRAINTS YIELD name RETURN name'):
            query('DROP CONSTRAINT `' + item['name'] + '`')
        for item in query('SHOW INDEXES YIELD name, type WHERE type <> "LOOKUP" RETURN name'):
            query('DROP INDEX `' + item['name'] + '`')
    log = []
    start = time.monotonic()
    for index, statement in enumerate(statements(loader), 1):
        t = time.monotonic()
        entry = {'index': index, 'statement': statement}
        try:
            query(statement)
            entry['status'] = 'ok'
        except Exception as exc:
            entry.update(status='error', error=str(exc))
        entry['seconds'] = time.monotonic() - t
        log.append(entry)
        (out / ('baseline_' + tag + '_load.json')).write_text(json.dumps(log, indent=2, ensure_ascii=False))
        print(json.dumps({k: v for k, v in entry.items() if k != 'statement'}), flush=True)
        if entry['status'] == 'error':
            break
    report = {'variant': tag, 'seed': args.seed if args.variant=='shuffle' else None, 'elapsed_seconds': time.monotonic() - start, 'completed': all(x['status'] == 'ok' for x in log), 'statements_executed': len(log), 'neo4j': query('CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition'), 'snapshot': snapshot()}
    (out / ('baseline_' + tag + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'snapshot'}), flush=True)


if __name__ == '__main__':
    main()
