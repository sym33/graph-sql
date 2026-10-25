Classification-based peer discovery

Offline replay from the release root:
  python3 reproduce.py transfer

This second question uses the frozen SAI, SL and ATC dictionary without tariffs
or route rules. The three D0 anchors are selected by a fixed hash procedure.
The expected answers enumerate source-code prefixes independently of native
SQL recursion and Cypher traversal. Replay checks complete source-bound outputs,
source ablation, absent anchors, a removed parent edge and replicated answers.
It verifies recorded native answer hashes; it does not repeat native timings.

Native replay (Linux; PostgreSQL 16 binaries, Java 21, Neo4j 5.26.1 archive).
First change to code/Transfer_Peers/:
  python3 setup_native.py --root /ABS/peer-test --neo4j-home /ABS/neo4j-community-5.26.1
  python3 model.py --root /ABS/release/.runs/work --output /ABS/peer-test/model.json
  /ABS/peer-test/venv/bin/python native.py --model /ABS/peer-test/model.json --output /ABS/peer-test/native_initial.json
  /ABS/peer-test/venv/bin/python native.py --model /ABS/peer-test/model.json --output /ABS/peer-test/native_control.json --plan-control

The setup creates user-owned test stores at PostgreSQL port 15432 and Neo4j
HTTP/Bolt 18774/18787, all loopback only. Use a new dedicated directory and
unused ports. The native runner clears the dedicated Neo4j store and replaces
witness/parent/seed tables in the dedicated PostgreSQL cluster. It does not
use the study's original stores. Stop instances after use:
  /ABS/peer-test/neo4j/bin/neo4j stop
  /usr/lib/postgresql/16/bin/pg_ctl -D /ABS/peer-test/pgdata stop

Initial SQL forms the ancestor relation for all recorded codes. The subsequent
exploratory control compares anchored recursion, preserving every output field.
Both SQL formulations and Neo4j are interleaved in that follow-up. Protocols
retain the sequence and selection rules. Disconnected copies increase storage
and answer volume; they do not add medical variety, density or hierarchy depth.
Native medians include full local HTTP responses and decoding. SQL uses a
Python HTTP bridge with sqlite3/psycopg2; Neo4j uses its native HTTP endpoint.
Shared ancestors express classification membership, not therapeutic equivalence.
