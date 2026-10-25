Paired implementation examples

From the release directory:
  python3 reproduce.py examples

This standard-library replay exports original study queries to
.runs/work/examples/results/ and checks explained discovery and route judgments
against the frozen physical graph exports. It also checks two SQL cache rebuilds.
It does not start or modify Neo4j. Original native measurements remain separate.

1. Find and explain candidates
   discovery.cypher and discovery.sql are the complete queries from
   Graph_Validation_V22/code/explanation_workflow.py. SQL receives a JSON string
   of rules as its single parameter; Cypher receives the same list as $rules:
   ["direct_SAI", "via_authorization_SL"].
   Input: source records, product-classification Associations/witness rows,
   their supporting-record links and tariff records. Output: product, ATC,
   tariff row, linking-rule and source-record identities/payloads. Compare the
   normalized complete rows, not just candidate counts. Expected D0 output:
   1,559 linking paths, representing 564 distinct product–tariff candidates.
   Schema and executable loaders: explanation_workflow.py and
   Source_Refresh/code/compare.py. The short article listing projects only keys;
   use these full queries when checking explanations.

2. Compare administration routes
   The same discovery outputs feed the shared assess(group, package, tariff,
   policy) function in Graph_Validation_V17/code/route_policies.py, exercised by
   explanation_workflow.py for both representations. Use policy exact_code.
   Examples: oral group + O -> VERIFIED; oral group + IV -> CONTRADICTED;
   generic parenteral package without an explicit route + IV -> UNDETERMINED.
   This implementation deliberately shares the interpretation layer. SQL and
   Neo4j retrieve its inputs; neither independently supplies the clinical rule.
   Missing or uninterpretable inputs stay UNDETERMINED. For candidate aggregation,
   use example.py:aggregate; keep all underlying package judgments and records.

3. Store and refresh connections
   store_connections.cypher and store_connections.sql are the original statements
   from Source_Refresh/code/compare.py. Neo4j saves CachedTariff relationships;
   SQL saves witness–tariff rows in candidate. Retain the witness/Association so
   the saved connection can still be traced to its source records.
   SQL invalidation: DELETE FROM candidate;
   Cypher invalidation: MATCH ()-[r:CachedTariff]->() DELETE r;
   These statements invalidate every such cache entry: use only the dedicated
   experiment database. Load the replacement sources before rematerialization.
   The offline example checks SQL rebuild equivalence on D0. The seven original
   native D0-to-D1 cycles, including source replacement, are in Source_Refresh/.
   A repeated SQL INSERT without invalidation is not an idempotent refresh.

Adaptation checklist
- State one useful domain question and the identifiers, judgments and evidence
  the answer must contain. Hand-specify small expected cases, including missing
  and conflicting information, before timing queries.
- Map source identities to entities; preserve original rows, source versions and
  linking rules. Specify which links are permitted across sources.
- Implement the same answer in each selected engine. Compare sorted complete
  records and repeated-row counts using the same interpretation rules.
- Add source updates and check that explanations and judgments are refreshed,
  even when the candidate keys stay unchanged.
- Measure representative queries, construction and intended refresh operations.
  Inspect slow plans; compare query-time and stored derivations. Choose from the
  local workload costs and separately assessed operational requirements.
