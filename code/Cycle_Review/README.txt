Classification-cycle review

From the release directory:
  python3 reproduce.py cycle-test

The three cases retain the earlier pre-timing identifier selection (Swiss,
tariff-associated, same-code peer): 31096, 41330, 44470. A cycle means two
Association records connect the same product to the same ATC concept. It is
an undirected connection pattern, not necessarily an error. Native results
contain 0, 1 and 0 cycles; the one cycle is Prothromplex, authorization 41330,
ATC B02BD01. The direct SAI and authorization-linked SL classifications share
the same SAI premise; the latter adds an SL premise. They are alternative
explanations, not independent confirmations.

observed/cycles.cypher returns the actual path for graph display. Set $product
to a case ID in Neo4j Browser. observed/cycles.sql returns the same identifiers.
The receipt retains complete result hashes and all timing samples. The replay
reconstructs equal SQL answers, checks the fixed-order variant and verifies
all 38,211 source-row identities against the frozen D1 files. It requires no
server and does not repeat timings.

Native medians: 7.3–9.0 ms; automatically planned embedded SQLite: 23.4–42.3 ms.
The subsequent within-SQL plan control gives 0.019–0.038 ms for fixed join order,
with identical predicates, indexes and answers. This separate control does not
rerun Neo4j. Interfaces differ (Neo4j HTTP versus embedded SQLite). The initial
configuration advantage cannot be generalized to a database-model advantage.

The graph figure separates the closed classification pattern from its source
premises. It suggests how a reviewer could inspect convergence and shared
provenance. No improvement in human speed or understanding was measured.
