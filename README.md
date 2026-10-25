# Graph–SQL medication experiments

Reproduce source-linked medication–tariff review and ATC classification-peer
retrieval with Neo4j, SQLite and PostgreSQL. Contains code, frozen inputs,
protocols and recorded measurements; no manuscript or generated databases.

## Run

Python 3.12. These checks need only the standard library:

```sh
python3 reproduce.py verify
python3 reproduce.py examples
python3 reproduce.py analysis
python3 reproduce.py cycle-test
python3 reproduce.py breadth
python3 reproduce.py tests
```

`breadth` checks all 5,678 eligible Swiss authorizations and 3,647 ChEMBL
molecules, source ablations and recorded outputs from 810 native retrievals.
Offline checks reconstruct results; they do not remeasure database timings.

For every offline analysis, install `requirements.txt` and Xpdf `pdftotext`,
then run `python3 reproduce.py all`. No source downloads are required.
Generated files stay in `.runs/`.

## Files and native reruns

- `code/`: executable analyses, SQL/Cypher, protocols and measurement receipts.
- `data/frozen.zip`: deduplicated inputs; `data/index.json` maps original paths.
- `MANIFEST.json`: code and input checksums.
- `DATA_SOURCES.json`: source origins and versions.

Native setup and rerun instructions: [peer retrieval](code/Transfer_Breadth/README.txt),
[database setup](code/Transfer_Peers/README.txt),
[cycle inspection](code/Cycle_Review/README.txt),
[paired examples](code/examples/README.txt).
Native reruns require dedicated databases; follow their reset instructions.
Original timing receipts are observations; lifecycle totals are calculated scenarios.

## Version and rights

Cite the exact study commit, not the moving default branch. A separately
archived release with a DOI is recommended for long-term preservation.
Original study software is MIT-licensed. Third-party code, data and documents
retain their providers’ rights: see `THIRD_PARTY_NOTICES.md` and
`DATA_SOURCES.json`.
