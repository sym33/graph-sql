Full-population and cross-source transfer

From the release root:
  python3 reproduce.py breadth

Standard-library replay checks every eligible Swiss authorization and ChEMBL
molecule at depths 0/2/4, for full and ablated classifications. Independently
expressed SQL adapters reconstruct source bindings from original CSV rows or
JSON arrays. Python prefix enumeration agrees with SQL closure membership.
It also reconstructs all complete native explanations and checks all 810
recorded retrieval outputs. Native timings are not repeated by this command.
Frozen ChEMBL inputs were already distributed as external-reference data;
no new source downloads, ontology service or medical labels are required.

Native replay, after the offline command has reconstructed .runs/work:
  cd code/Transfer_Breadth
  python3 study.py --root /ABS/release/.runs/work --export /ABS/models.json
  /ABS/peer-test/venv/bin/python native.py --models /ABS/models.json --output /ABS/peer-test/breadth/native.json

Use the dedicated-instance setup in ../Transfer_Peers/README.txt. Native replay
uses only the dedicated PostgreSQL 15432 and Neo4j HTTP 18774 stores. It
replaces witness/parent/seed tables and the experiment-specific Neo4j labels.
Stop the test instances with the commands in that README after use.

The two source corpora retain their own identifiers and source scopes.
ChEMBL molecules are not projected to Swiss authorizations or parent families.
Memberships mean classification peers, not clinical substitution. Global and
anchor-started SQL, Cypher and the complete answer schema remain unchanged
between corpora. Nested hash-ranked real-entity subsets plus fixed anchors
vary source coverage, occupied branches and degree; no copies are used.
Protocols disclose the preceding pilot and the exploratory study status.
