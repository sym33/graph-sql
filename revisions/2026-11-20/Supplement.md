# Supplementary Materials

Graph vs. Relational Databases: How Sources and Workloads Shape the Choice in Medication–Tariff Review

This document supplies the rules, checks and execution conditions needed to interpret the manuscript. S1–S11 are sections of this single supplement. D0 is the frozen baseline; D1 replaces only Swiss product authorizations from Refdata’s SAI catalogue and the Specialities List (SL) package extract. A separate comparison extract is used in secondary checks and is not D1. V, C and U denote compatible, conflicting and undetermined outcomes under a declared rule. Citation numbers refer to the manuscript.

Supplementary_Data.zip provides an evidence index, the complete detailed documents and six original code/result archives. It retains full tables, source coordinates, queries, protocols, raw observations and verification scripts. The original frozen reproduction base remains available at the DOI given in the manuscript. Thus a reader can follow the analytical procedure here and inspect or replay the underlying evidence without treating the full archive as required narrative reading.

## S1. Answer specification and computational validation

An answer is specified by entity keys, returned fields, source records, interpretation status and row multiplicity. A separate implementation reconstructs it from frozen inputs; count agreement alone is insufficient. Checks cover source identity, literal field attribution, product/premise binding, snapshot and authority scope, informative content and field agreement. Unavailable context leaves the requested claim U while retaining any authenticated frozen-field conflict.

Thirteen controlled operations per selected classification or indication unit yield 665,509 single-defect cases, all with the specified outcomes. Classification uses one witness per product–ATC pair (8,155 comparison-extract and 8,163 D0 units); indication uses all witnesses (17,428 and 17,447). Five representation/order transformations over 18,339 comparison-extract witnesses give 91,695 invariant checks. All 64 combinations of six Boolean obligations are exhausted. Omitting individual obligations admits constructed false confirmations; complete omission counts are archived.

Shapes Constraint Language (SHACL) checks cover 1,040 stratified cases and 480 mixed-failure classification cases, agreeing with imperative and independently expressed SQL decisions. All 2,997 three-policy route certificates conform; seven mutation families produce 20,979 rejected certificates, including 63 stratified mutants rejected directly by pySHACL. Complete graph/relational checks also agree on 104,682 D0 context decisions and 18,509 content-eligible recorded EMA Medical Subject Headings (MeSH) pair-and-term outputs. These are dependent specification checks. They establish consistency with the declared rules, while S7 addresses selected documentary references.

## S2. Identity policies and external classification access

Reference identity is resolved before the ATC value is compared. Exact preferred-name or synonym matching must identify one ChEMBL parent; the asserted ATC never selects that parent. An exploratory lexical policy retains, removes or replaces terminal Latin “um” with “e” for names of at most four tokens. All exact candidate-name matches must agree on one parent. A further gate requires newly resolved SL fields to share a Refdata substance ID for the same authorization.

Table 1. D0 SL identity access. Coverage concerns reference access under the stated policy, not product-level chemical equivalence.

| Policy | Resolved rows | Exact external support | Remaining boundary |
| --- | --- | --- | --- |
| Exact names | 545 | 517 | 9,720 unresolved; 28 discordant |
| Official synonyms | 545 | 517 | No additional resolution |
| Lexical candidates | 5,979 | 5,946 | 4,286 unresolved; 30 discordant; three temporal |
| Additional source-ID gate | 5,907 | 5,874 | 72 new identities withheld |

Lexical expansion adds 5,434 package rows across 1,790 authorization–substance fields; source IDs support 5,362 and withhold 72 across ten fields. Withheld examples include iodine/contrast-agent declarations, tenofovir/tenofovir-disoproxil and silymarin/plant-extract granularity. Access rises from 5.31% to 58.25%, or 57.55% with the additional gate. Full candidate identities and crosschecks are archived; the manuscript appendix separately reports EMA reference coverage.

## S3. Derivation rules and matched representations

Four property chains derive: recorded classification → tariff connection; historical classification → historical review connection; recorded classification → dictionary-supported broader group; and a source-row ingredient declaration → its witness's documentary tariff connection. Swiss documentary admission requires scoped product identity, direct SAI or authorization-linked SL classification, exact tariff-code equality and the frozen tariff version. Historical and European-only paths retain separate targets; European paths need a Swiss identity bridge to enter the Swiss target.

SQL independently reconstructs candidates and declaration pairs. OWL-RL materialization and native Cypher are compared with these outputs, while SHACL checks types, premises, endpoints, snapshots and historical separation. Removing a chain tests its intended dependencies. The complete D0 outputs include 1,559 documentary derivations, 564 candidates, 468 authorizations, 179 tariff records, five historical derivations, 324 withheld European paths, 5,204 broader-group derivations and 999 tariff pairs for 837 source-row ingredient declarations.

Nine challenges per documentary derivation give 14,031 cases. Faithful controls pass; applicable field conflicts are contradicted; missing sources, wrong endpoints, unavailable versions and unsupported payment targets remain U. All five historical and 324 European paths remain U when promoted to Swiss documentary targets. Five structural fixtures check missing premises, types, snapshots and historical leakage. Stored variants preserve each witness–tariff link and its premises as a graph relationship or indexed SQL row; query-time variants derive it when requested. Rules, adapters and full results are archived.

## S4. Interpretation, source updates and execution procedure

### Routes and the next evidence request

Coarse assessment maps oral and parenteral group tokens to families; exact assessment recognizes oral, IV, SC, IM and IT, including “subkutan” as SC. Word boundaries guard partial matches. Generic parenteral or infusion wording leaves the exact route U. Recognized overlapping options give V; fully interpreted disjoint options give C; insufficient specificity gives U. The ancillary formulation field additionally requires selected tablet/capsule or infusion/injection/powder wording in the same record. It measures lexical availability, not a validated formulation classification.

Candidate aggregation returns V for any V package comparison, otherwise C if all comparisons are C, and U otherwise, including no packages. All contributing package comparisons agree within each candidate/policy in these populations, so existential, unanimous and conflict-first summaries coincide here. Inventories support route noncoverage only when complete under the extraction rule. Source attribution, historical code compatibility, current applicability and payment conditions remain distinct assessment targets.

The next request follows prerequisite order: obtain package context; inspect a finer-policy conflict; obtain an explicit route; obtain formulation wording; otherwise retain supported context. D0 request counts are 137/36/289/10/92 in that order, and D1 counts 138/36/298/10/93. Monitoring membership, then judgments, then requests flags 19, 29 and 31 of 579 union keys. Ten shared keys change judgments and requests; two change requests alone. The twelve shared request-changing keys persist across six tested priority permutations, although only three preserve route-before-formulation order and the selected request can change.

Retsevmo tablets (70214; ZE-2026-263; L01EX22) have no linked D0 package. Two D1 SL records describe oral 40 mg and 80 mg tablets, changing all three policy summaries from U to V and the next request to retaining context. Bortezomib Zentiva (68344; ZE-2026-51) loses its D0 1 mg and 3.5 mg package records: coarse V becomes U, while exact/formulation U persists and the request moves from explicit route to package evidence. Flixabi (70087) and Eltrombopag Devatis (70153) instead gain package context while retaining U judgments. Exact before/after rows and hashes are in Reviewer_Controls.zip, case_evidence/selected_cases.json and the follow-up census. Reviewers would check scoped identity, presentation, date and tariff conditions before acting on these documentary summaries.

### Dependency checks and optional acquisition

Single-record perturbations cover 837 D0 and 853 D1 package records. Six changes per record–state combination yield 10,140 graph/SQL-agreeing answers. Five loss/missingness conditions introduce no candidates in 8,450 trials; valid-shaped reassignment adds candidates in 1,686 of 1,690 reset trials. Four cache-update operations give 6,760 cases in which the stale reference differs from reconstructed SQL; rebuilding restores equality and is idempotent. Duplicate insertion changes premises/multiplicity while retaining judgments. These offline checks reuse route/aggregation functions and do not add native lifecycle observations.

Optional evidence-acquisition calculations consider finite domains for missing source fields. Gain bounds range over permitted completions, retaining a shared value for repeated references to one field. Independent checks cover 320 fixtures, 980 completed worlds and 196 preservation probes. Jointly useful fields and redundant fields prevent treating single-field bounds as a globally optimal acquisition order. Route masking, strength-unit compatibility, extraction-cost assumptions, all budget tables and the fifteen ancillary source references are retained in the detailed S4 document. They concern documentary resolution and exclude actual administered dose, network cost and human review effort.

### Native timing and transfer

The historical tariff environment is Linux 6.8.0-117, Python 3.12.3, SQLite 3.45.1 and Neo4j Community 5.26.1 on a Xeon Silver 4416+ host reporting 80 logical CPUs and 1,081,833,316,352 bytes RAM. Neo4j uses a 1–2 GiB heap/1 GiB page cache; SQLite begins with default connection settings. Keys cover products, concepts, records, snapshots, rules, witnesses, indications and tariffs; indexes cover classification codes, product/rule and jurisdiction/rule, reverse premises, source files, indications and cached tariffs. SQL ANALYZE follows loading/materialization; Neo4j constraints/indexes are awaited. SQLite uses committed local inserts and Neo4j transactional HTTP batches of 500, so load costs include different native interfaces. Exact schemas, queries and EXPLAIN records are archived.

Retrieval timers cover local HTTP request, complete transfer and decoding; sorting, hashing and reference comparison occur afterward. Three warmups precede fifteen interleaved repetitions; seven cycles measure loading, materialization, invalidation, replacement and reconstruction. Ordered SQL replaces inner JOIN with CROSS JOIN while preserving predicates. Every original 840 output agrees, including refreshed answers. Cycle-query embedded SQL timings form a separate within-SQLite plan control, not a matched HTTP engine comparison.

Classification-peer retrieval admits seven-character dictionary codes and zero/two/four parent steps per side. Global and anchor-started SQL recursion and Neo4j return complete entities, codes, ancestors, depths and source premises. Fourteen fixed anchors are queried as a batch over three nested real-entity subsets in each Swiss/ChEMBL corpus. Two warmups and nine interleaved repetitions give 810 matching outputs; PostgreSQL 16.13 uses 1 GB shared buffers/64 MB work memory. Full censuses, code-ablation results, degree distributions and anchor concentration are archived. This transfers the procedure across sources within ATC; batch times are not per-entity population latency estimates.

## S5. Curation, aggregation and workload coverage

Revision_Analysis.zip retains focus_analysis.py and results for candidate profiles, ATC overrides, formulation availability and the full peer census. These analyses were specified after timing and are exploratory. Of 22 configured overrides, seven alter D0 values and six D1 values; reversal preserves the 564/575 complete candidates and shared judgments while changing source attribution. D0 raw values use archived attribution; D1 additionally uses frozen XML. A staging override alone does not establish the currently authorized code. All aggregation alternatives agree because no within-candidate mixed package profiles occur. Exact profile tables and lexical-boundary examples remain in detailed S4 and the code archive.

## S6. Catalogue versions and source provenance

The 185 base definitions pool SwissDRG ZE, TARPSY TZE and ST Reha RZE: 182/2/1 definitions retaining V15.3/T6.3/R3.3. D0 candidate counts are 535/26/3 and D1 counts 545/27/3. All 182 ZE signatures agree with official November 2025 and April 2026 releases on ATC, route, dose unit and qualifier; separate official documents corroborate the other three routes. November 2025 EDV documentation refers the va field to the 2023 technical companion, Section 3.1.c. Dose bands and other billing conditions remain outside route comparison. LLM_Document_Audit.zip retains analysis/source_snapshot_manifest.json, official_ZE_signatures.csv, tariff_audit.json and exact source URLs, hashes and locators.

## S7. Official-reference and cross-jurisdiction checks

Reference_Validation.zip contains protocols, keyed comparisons and document locators for the 101 stratified package–tariff cases (74 authorizations; 92 pack keys) and eight selected Swiss–EU comparisons. Swissmedic lists dated 30 September 2026 were retrieved on 26 October 2026. All keys are present; SAI staging ATC agrees exactly for 73/74 authorizations and SL ATC for 100/101 comparison rows. Spinraza has M09AX07 in staging and broader M09AX in the reference. Only seven normalized authorization names match; keys establish identity before classification comparison.

The Swiss–EU cases match ingredient, strength and formulation/device while preserving national identities: two Entyvio devices, two Rybrevant SC strengths, Ocrevus SC, Darzalex SC, Actemra/RoActemra pens and Luxturna. Routes agree in all eight across six EMA documents. Shared sponsor/regulatory origins limit independence; current concordance does not establish historical presentation continuity or payment entitlement. Complete passage coordinates and document identities are archived; full retrieved product-information documents are not redistributed.

## S8. Ancillary model-assisted extraction

These existing checks assist extraction and source comparison; they neither define candidate/timing outputs nor provide a human expert standard. Two isolated general-purpose LLM contexts assessed 101 comparisons with algorithm labels withheld and 65 distinct Swiss professional-information documents per reader; a third examined disagreements before unblinding. Current route-overlap directions agree in all 101; conservative presentation identity remains unresolved in five. Historical D0 applicability was not established; the interface exposed neither a versioned model identifier nor sampling parameters.

A separate model-family check supplies identical tariff-blinded excerpts in 67 requests each to Llama 3.3 70B and Qwen 2.5 32B, using the archived quantization/runtime settings. Locked structured responses cover 98/99 cases; current routes agree in 92/96 paired cases. Mechanical citation checks fail in 64/98 and 13/99; three truncated outputs account for five missing cases. Citation-line presence does not establish entailment, and identity/history fields are unreliable. LLM_Document_Audit.zip and Reference_Validation.zip/Model_Family_Audit.zip retain locked responses, settings, weight digests and replay code. These are sensitivity checks, not accuracy estimates.

## S9. Conditional serial-cost calculation

Decision_Analysis.zip contains the calculator, historical component inputs, plots and 600 scenarios. Each assumes one build, Q requests, U full replacements and context fraction p: C = B + U × R + Q × [p × T_context + (1 − p) × T_peer]. T_peer is tariff-peer/indication retrieval, distinct from ATC hierarchy retrieval. Stored materialization/upkeep enter B/R. Loading uses D0 and retrieval uses D1; zero replacements therefore use a load proxy. Repeated replacements assume unchanged unit costs.

The grid combines five request counts (10–100,000), ten replacement counts (zero–1,000) and twelve context shares, sampled more finely near 99.36%. Component Q1/Q3 corners and independent ±10% perturbations are deterministic sensitivity bounds, not confidence intervals or probabilities of winning. Engine bounds minimize over its tested configurations; strict separation requires an upper cost below competitors' lower costs. SQLite separates in 490 cells and 110 remain unresolved. Scenario counts are planning assumptions, not observed workload frequencies. PostgreSQL is assigned no tariff lifecycle cost. Deployment integration, maintainability, reviewer usability and service-level acceptance require separate local evidence.

## S10. Initial cache and directly timed lifecycle controls

The exploratory protocol was saved before the 20 November 2026 measurements. Frozen source hashes and complete references remain unchanged; this session does not replace historical model inputs. SQLite uses the same indexed 74,301,440-byte file, 4096-byte pages and fixed-order SQL. Arms are default cache_size=-2000/mmap_size=0; cache_size=-1048576; and that cache plus mmap_size=1073741824. Journal mode is DELETE, synchronous 2 and temp_store 0. Neo4j retains a 1–2 GiB heap and 1 GiB page cache in a dedicated instance.

Three blocks randomize SQLite arm order, with Neo4j separately after SQLite. Three warmups and fifteen repetitions give 45 observations per condition and 720 equal complete outputs: 1,018 context rows or 478 tariff-peer rows each. Thus this is a cache-capacity experiment, not randomized matched-resource engine evidence. Allocator/reference memory and different execution histories preclude reading process RSS as an engine-only memory ratio; exact settings, usage and all retrieval distributions are archived.

Seven randomized repetitions of four engine/strategy variants directly time build D0 → replace D1 → 100 context requests. Stored variants include materialization, invalidation and reconstruction; SQLite uses a fresh file and includes ANALYZE after replacement. Schema creation, service start, reference construction and answer checking are excluded; native loading, commits, upkeep and full HTTP consumption are included. Seven complete D1 task answers are checked after each cycle.

Table 2. Observed total medians [Q1–Q3], seconds, over seven cycles per variant. The adjacent estimate uses those same runs' phase medians and 100 × pooled request median. Error = (estimate/observed − 1) × 100.

| Engine / strategy | Observed seconds | Estimate seconds | Error % |
| --- | --- | --- | --- |
| SQLite query-time | 6.80 [6.46–7.31] | 7.10 | +4.31 |
| SQLite stored | 6.19 [5.29–7.74] | 5.42 | -12.46 |
| Neo4j query-time | 37.80 [35.02–38.24] | 32.89 | -13.01 |
| Neo4j stored | 32.50 [20.98–37.10] | 29.97 | -7.79 |

These 28 workflows test one horizon, not all 600 assumed mixtures or concurrent/cold-cache behavior. Quartiles use Python statistics.quantiles with its default exclusive convention. Reviewer_Controls.zip retains protocol, executed code, raw samples, schema/queries, estimated plans and untimed final-state plan audit. Its verify_controls.py checks saved results and timer coverage without starting database services.

## S11. Randomized resource controls and cost decomposition

### Resource comparison

Three services—Neo4j and two SQLite workers—have equal 4/8 GiB memory.max, memory.swap.max=0 and cpu.max=200000/100000 microseconds. Every service thread is verified on CPUs 20–21; the client uses 22–23. The initial cpuset-delegation precheck failed before timing. The amended taskset-affinity procedure and failed log are retained. Actual limits are read before each block; the shared OS cache stays warm and CPU exclusivity is not claimed.

Versions, queries, schemas and answer contracts match S10. Neo4j retains its heap/page-cache settings; SQLite compares default and 1 GiB cache without mmap. Six balanced shuffled blocks comprise three blocks per budget; each uses three warmups and fifteen repetitions per condition, randomly interleaving twelve engine/cache/task/strategy conditions. There are 24 budget-specific conditions, 45 observations each and 1,080 equal complete outputs. These are technical repetitions of the same deployments, with HTTP execution/serialization included.

\Needspace{19\baselineskip}

Table 3. Randomized retrieval medians [Q1–Q3], milliseconds. QT = query-time; S = stored derivation. Cache denotes the SQLite 1 GiB allowance; Neo4j uses a 1 GiB page cache.

| GiB | Configuration / strategy | Context | Tariff peers / indication |
| --- | --- | --- | --- |
| 4 | SQLite default QT | 37.55 [36.23–38.45] | 128.32 [126.17–129.88] |
| 4 | SQLite default S | 40.13 [39.22–41.84] | 169.39 [167.26–172.51] |
| 4 | SQLite cache QT | 31.78 [30.54–33.11] | 116.84 [115.75–120.21] |
| 4 | SQLite cache S | 35.19 [33.98–36.55] | 149.30 [146.88–151.42] |
| 4 | Neo4j QT | 154.73 [151.36–158.90] | 1145.42 [1137.04–1153.16] |
| 4 | Neo4j S | 38.63 [37.57–40.35] | 699.68 [690.74–708.57] |
| 8 | SQLite default QT | 36.91 [36.02–38.47] | 127.88 [126.79–129.11] |
| 8 | SQLite default S | 40.24 [39.23–41.29] | 171.32 [168.45–175.58] |
| 8 | SQLite cache QT | 32.29 [31.05–33.65] | 117.42 [116.00–119.32] |
| 8 | SQLite cache S | 34.88 [33.44–35.74] | 148.84 [147.25–152.44] |
| 8 | Neo4j QT | 153.96 [149.15–157.72] | 1156.31 [1142.09–1168.40] |
| 8 | Neo4j S | 39.58 [37.20–41.21] | 702.03 [692.14–725.07] |

Tuning reverses the stored-context median ordering at both budgets. Actual charged service memory remains unequal: Neo4j approximately 1782.8–1785.6 MiB, SQLite default 19.3–19.4 MiB and enlarged cache 35.4–35.5 MiB across the recorded blocks. Neither budget produces an OOM event. These descriptive results concern the stated queries and working set, not a memory-exhaustion threshold. Complete resource records and paired observations are archived.

### Aggregation and session differences

Using one time unit, let $P_i$ sum cycle $i$’s loading/upkeep phases, $B_i$ its 100 requests and $T_i$ its outer elapsed time. Let $P$ sum the individual phase medians, and $E$ be 100 × the pooled request median. The estimate error $P+E-\mathrm{median}(T_i)$ is exactly the sum of:

1. Phase aggregation: $P-\mathrm{median}(P_i)$.
2. Combining blocks: $\mathrm{median}(P_i)+\mathrm{median}(B_i)-\mathrm{median}(P_i+B_i)$.
3. Request extrapolation: $E-\mathrm{median}(B_i)$.
4. Timer residual: $\mathrm{median}(P_i+B_i)-\mathrm{median}(T_i)$.

Signed terms can cancel; they are accounting components, not independent causal effects.

For query-time Neo4j's -13.01% error, phase aggregation contributes -0.15 percentage points and single-request extrapolation -11.47. Replacing $E$ by $\mathrm{median}(B_i)$ gives errors of +1.12%/−1.67% for query-time/stored SQLite and −1.54%/+5.51% for Neo4j. This changes the estimator on existing observations. Full signed tables and independent recalculation are archived.

Historical and later-session components are also reconciled separately. Stored Neo4j's 17.19 s historical estimate becomes 32.50 s observed: +1.66 s base loading, −0.05 s upkeep, +11.16 s query-parameter change and +2.53 s remaining estimate/outer-total gap. This is an accounting identity; missing historical telemetry cannot identify a unique cache, JIT or host-load cause.

A prespecified three-pair contrast randomizes zero versus thirty post-replacement warmup queries under the same 4 GiB CPU/affinity conditions, then times 100 requests per arm. All 600 answers agree. Block times without/with warmup are 4.068/4.131 s, 17.108/3.654 s and 3.778/3.720 s. Two near-null contrasts and one slower unwarmed block do not establish a stable warming effect. Followup_Controls.zip retains protocols, all observations and the exact decomposition; run python3 code/verify_followup.py after extracting it to check saved results without running databases. Native reruns need the recorded software, frozen base and adapted dedicated paths.
