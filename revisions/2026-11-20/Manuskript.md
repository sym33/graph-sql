# Graph vs. Relational Databases: How Sources and Workloads Shape the Choice in Medication–Tariff Review

Christian Franke^a,b^ and Murat Sariyar^a,*^

a. Bern University of Applied Sciences, IODA Institute, Bern, Switzerland

b. SwissDRG AG, Bern, Switzerland

Correspondence: Murat Sariyar, Bern University of Applied Sciences, Quellgasse 21, CH2502 Biel/Bienne, Switzerland; E-mail: murat.sariyar@bfh.ch.

ORCID (Murat Sariyar): https://orcid.org/0000-0003-3432-2860

Prior publication: This article substantially extends Franke and Sariyar, “Modeling Reimbursement-Relevant Drug Data as a Property Graph” (2026), doi:10.3233/SHTI260918. It adds controlled curation and source-replacement analyses, matched graph–relational benchmarks, classification-peer transfer experiments, and reproducible workload-based decision analyses with an executable reproduction package.

## Abstract

Medication–tariff review identifies possible links between medicinal products and add-on payment definitions, then examines the product evidence supporting each link. Classification codes locate candidates, while administration routes help assess their documentary compatibility. We distinguish changes in this information from the database time required to retrieve it. Frozen Swiss source extracts are evaluated in a graph database, Neo4j, and a relational database, SQLite, with complete-output checks before execution comparisons. The baseline contains 564 product–tariff candidates, including four found through package-linked classifications. Exact-route assessment identifies six subcutaneous–intravenous discrepancies concealed by coarse grouping. Source replacement produces 575 candidates and changes the next evidence request for twelve shared candidates; two retain unchanged judgments. Tracking the missing prerequisite therefore reveals changes that judgment-only monitoring misses. Both implementations return the same requested evidence, but their timing order depends on configuration. With precomputed links and a 4 GiB ceiling, retrieving combined source context takes median 40.13 ms in default SQLite and 38.63 ms in Neo4j; a 1 GiB SQLite cache allowance lowers its median to 35.19 ms. Direct workflows examine how request-time variation affects total processing time, and classification retrieval tests reuse across Swiss products and ChEMBL molecules. These results support database selection based on the required evidence, configuration and update/request workload.

**Keywords:** medication data integration; source curation; evidence updates; property graph; relational database; provenance; reproducibility

## Introduction

Medication–tariff review connects two kinds of catalogue. Medication catalogues describe medicinal products and their presentations, such as a tablet or injection. Reimbursement catalogues define conditions under which additional payments may apply. The review first identifies possible product–definition links and then examines whether the available product records document the relevant conditions. In Switzerland, SwissDRG AG publishes these definitions for acute care (Swiss Diagnosis Related Groups, SwissDRG), psychiatry (TARPSY) and rehabilitation (ST Reha).

Drug classification helps identify candidate links, but a shared code supplies only part of the evidence needed to interpret them. The Anatomical Therapeutic Chemical (ATC) system groups medicines in a code hierarchy. A subcutaneous presentation can share a code with a tariff definition requiring intravenous administration, so the reviewer also needs presentation-specific route information. Maintaining these links requires accounting for vocabulary updates [1] and variation in ingredient, strength and dosage-form descriptions [2]. The practical scale of this problem is illustrated by a Swiss hospital study in which 579 of 1,086 antibiotic-product mappings required correction, often for route, amount or concentration [3].

Even when the set of candidates stays the same, an updated source can change what is known about them. A newly linked package may supply a route, or it may supply only enough context to reveal that an explicit route is still missing. Preprocessing edits can also change which source receives credit for finding a candidate: an edited direct code may reproduce a link supplied only by package evidence in the uncorrected view. To explain these effects, an answer needs its provenance—the source records, versions and linking rules supporting it—and the prerequisite still unresolved. Comparing only candidate lists or final judgments can conceal a change in the next useful review step.

These information requirements also define what a database comparison should hold constant. A property graph stores records and connections as nodes and typed links; a relational database stores them in tables joined through identifiers. Both can represent the evidence needed here, while query formulation, indexes and workload affect retrieval time [4–7]. The earlier MediGraph study [8] integrated reimbursement-related drug sources in Neo4j and demonstrated exploratory traversal. We extend it with controlled source comparisons and a relational implementation, checking complete requested answers before interpreting execution differences [9]. Execution cost throughout this paper means processing time, including the stated interfaces, rather than financial expenditure or reviewer effort.

Three research questions organize this separation. **RQ1:** How do source linkage, curation and replacement change candidates, route judgments, provenance and the next evidence request? **RQ2:** Do graph and relational implementations preserve complete requested answers, including supporting records and repeated rows, across the tested changes? **RQ3:** How do query formulation, stored derivation and request/update counts and mixtures affect measured latency and calculated serial processing time? Answer agreement in RQ2 is a prerequisite for interpreting RQ3; resource settings, interfaces and timing boundaries must also be stated. A second task, retrieving products or molecules that share an ATC code or ancestor, examines reuse of the procedure. The analyses combine established provenance, output checking and benchmarking techniques in a partly exploratory design.

## Related Work

The information that a medication knowledge graph needs to preserve depends on the question it serves. DrugBank 6.0 expands curated drug information and jurisdiction-specific regulatory coverage [10], while CPMKG attaches conditions to drug effects and indications for precision-medicine queries [11]. Pharmacist-oriented retrieval [12], consumer medication questions [13] and cardiovascular guideline integration [14] require different selections of product, presentation and contextual information. Reimbursement exploration [8] and claims-risk estimation [15, 16] add administrative tasks. These applications motivate defining the intended answer before choosing a representation or comparing its execution.

Obtaining that answer depends on how records are transformed and linked. PheKnowLator automates customizable representations and evaluates the construction of twelve biomedical benchmark graphs [17]. The community-quality preprint by Cortes et al. assesses construction, documentation and dissemination criteria across sixteen graphs [18], and the preprint by Hu et al. shows that alignment coverage and failure modes vary with entity type and matching method [19]. Together with validated transformation in the SPHN Connector [20], this work supports recording the identities and transformations underlying an integrated result. Here, controlled source interventions use those records to explain changes in candidate support, documentary judgments and missing evidence.

Explaining an update requires both a record of the change and an assessment of its consequences. Provenance models describe contributing data and transformations [21–23]. Structural constraints can be checked with the Shapes Constraint Language (SHACL), while data-quality methods assess fitness for use [24–26]. Vocabulary maintenance and temporal-graph work address changing data [1, 27]. Dibowski's traceability system records triple-level updates with provenance and reconstructs earlier graph states [28]. Such histories locate changed assertions. Their significance for medication–tariff review depends on whether the change affects candidate membership, route interpretation or the prerequisite needed next.

Evidence verification addresses the support for the assertions themselves. Wei et al. use multitask learning to verify biomedical triples against expert-annotated examples [29], while the BioKGBench preprint combines scientific claim verification and graph question answering in an agent task for checking graph facts [30]. These assessments complement change histories: knowing which record changed and whether an assertion is supported still leaves the task-specific question of how the change affects the review.

The closest methodological neighbors for this question are the Evidence-Carrying Validation and KGI-Bench preprints. Evidence-Carrying Validation retains passing and failing evidence to guide repair [31]; KGI-Bench evaluates integration outputs through coverage, correctness and consistency [32]. Our analysis connects these evaluation concerns to the next unresolved prerequisite in medication–tariff review. If a new record supplies package context but leaves the route unspecified, the judgment can remain unchanged while the next evidence request changes. Comparing membership, judgment and request separately makes that transition observable. Requiring both database implementations to reproduce its supporting records then connects the information assessment to execution cost.

Execution benchmarks address the cost of returning a defined answer. Matched graph–relational comparisons use shared data and tasks to establish that basis [4–7, 9, 33]. Han and Tian study centralized and distributed Nebula Graph deployments for drug knowledge, including multi-hop and concurrent retrieval [34]. Their contrast examines deployment scaling within a graph system; ours compares graph and relational implementations while preserving complete review outputs and accounting for source replacement. FinBench incorporates skew, recursive filtering, repeated edges and read/write mixtures [35], and the GRBench preprint examines controlled graph–relational query series [36]. These designs show why a timing result needs its task structure, execution strategy and workload to be interpretable.

The strength of the answer check also matters. Graphiti formally checks relationships between Cypher, Neo4j's query language, and SQL, used by the relational implementations, within supported language fragments [37]. Our independent reference comparisons instead test complete-output agreement on the specified snapshots and interventions. They include source records and repeated rows, so the timed variants must return the same requested evidence as well as the same candidate keys.

Once the missing prerequisite has been identified, a further question is how to acquire evidence that could resolve it. Incomplete-data reasoning, query-driven matching, targeted cleaning and sensitivity analysis [38–41] inform the optional calculations in Supplement S4. Those calculations examine the availability and acquisition cost of additional fields. They extend the review workflow from locating an unresolved step to considering which evidence to seek next.

## Materials and Methods

We first fix the source files and identify their records, then derive possible product–tariff links and assess the recorded administration routes. Comparing source states reveals changes in membership, supporting evidence and the next unresolved prerequisite. Independently reconstructed answers provide the reference for checking database outputs; timing then measures the work required to deliver those answers (Figure 1).

These stages use distinct counting units. A candidate is one product–tariff-definition pair; a supporting path records how that pair was found, and several paths may support one candidate. A package–tariff comparison assesses the route recorded for one package against one definition and contributes to the candidate summary. Complete requested outputs retain the relevant keys, interpretation fields, source identities and repeated rows. To distinguish causes, source interventions hold the rules fixed, rule comparisons hold the sources fixed, and execution comparisons hold both fixed.

### Source states and matched data models

The baseline state, D0, consists of thirteen source extracts with 38,147 records: Swiss product authorizations from Refdata's SAI catalogue, Specialities List (SL) packages, European Medicines Agency (EMA) metadata, classifications and SwissDRG AG tariff definitions [42, 43]. A Swiss authorization anchors the product linkage; a package record describes a particular strength and presentation. D1 replaces only SAI and SL, giving 38,211 records while retaining the other eleven extracts and the tariff catalogue [44, 45]. The separate classification-retrieval task uses molecule-level ATC assignments from ChEMBL 37 [46]. Table 1 identifies each source's role and entity scope.

Source-file checksums, row positions and versions make each input record recoverable. Equal nonempty Swiss authorization numbers join SAI products to SL packages; package identifiers and European record identities retain their source-specific scopes. Before integration, preprocessing applies 22 configured ATC overrides, of which seven change a D0 field and six change a D1 field relative to raw recording. We reverse those edits separately to test their effect on source-attributed coverage. Archived attribution records identify the D0 raw values, and frozen XML additionally checks D1, preserving the distinction between recorded and curated classifications.

Tariff rows contain dose bands, but candidate discovery uses their underlying base definitions. Projecting the rows gives 185 definitions: 182 SwissDRG ZE, two TARPSY TZE and one ST Reha RZE, denoting add-on definitions in the three care settings. Each retains its catalogue version, ATC code, route, dose unit and qualifier. Dose bands remain available for subsequent eligibility assessment. S6–S7 provide the official catalogue checks and exact source identities.

Table 1. Source roles and relation scope.

| Data source | Role in the evidence layer | Interpretation |
| --- | --- | --- |
| Swiss product authorizations (Refdata/SAI) | Direct classification; authorization anchor; application text | Swiss product authorization and recorded fields |
| EMA medicine metadata | Direct classification; Medical Subject Headings (MeSH) terms; indication text | EMA medicine and separately typed fields |
| Swiss Specialities List (SL) | Classification joined through equal authorization identifiers | Swiss package-catalogue classification |
| German Federal Joint Committee (G-BA) indication assessments | Grouped International Classification of Diseases (ICD) context and original fields | German assessment context |
| World Health Organization (WHO) ATC dictionary and alterations | Dictionary and historical-code candidates | Named index and recorded alteration |
| ChEMBL 37 ATC-bearing molecules | Separate source corpus for classification-peer transfer | Molecule-record identities and recorded code arrays |
| SwissDRG AG tariff extract: SwissDRG ZE, TARPSY TZE and ST Reha RZE | Code-based candidate generation from base definitions | Separate catalogue/version identities; route comparison excludes dose-band and other payment conditions |
| SwissDRG technical companion | Administration-route definitions | Explicit administration-code meanings |
| ATC/defined daily dose (DDD), benefit assessments and SwissDRG contextual lists | Supporting source context | Background information outside the primary comparisons |

The two database models represent the same source records and links. In Neo4j, an Association node connects a recorded classification to its product reference, ATC concept and supporting rows [47]; SQLite stores the corresponding objects in related tables. With tariff matches stored for reuse, the D1 graph contains 84,672 nodes and 177,044 directed relationships, including 8,416 source-specific product references and 2,196 ATC concepts. These references preserve their source identities. Neo4j identifier constraints [48] and SQL keys enforce the declared identities; S4 details graph composition, schemas and indexes.

**Figure 1. Separating source contribution from implementation cost.** The same comparison procedure is applied to tariff review and classification-peer retrieval. Removing or restoring a source path tests its additional contribution. Implementation timings are interpreted after complete expected answers, including supporting records, agree. Tariff review includes construction and source replacement; the three-engine peer comparison varies source populations, hierarchy depth and population size for retrieval.

### Candidate generation and route assessment

A candidate is admitted when a frozen tariff definition has the same ATC code as either the direct SAI product record or an SL package linked by authorization number. Each supporting path retains the record and linking rule used [21, 22, 49]. Removing a classification path while retaining product identity and package context isolates its contribution to discovery. Historical classifications and European references are assessed in their own source contexts.

For the admitted package–tariff comparisons, route assessment asks whether the recorded package fields document a route allowed by the definition. The coarse policy compares oral and parenteral families, grouping the injection and infusion routes together. The exact policy distinguishes explicit oral, intravenous (IV), subcutaneous (SC), intramuscular (IM) and intrathecal (IT) recordings using the SwissDRG glossary [50]. Recognized overlapping options are compatible (V); fully interpreted disjoint options are conflicting (C); insufficient specificity remains undetermined (U). Generic infusion or parenteral wording therefore leaves the exact route U. A separate formulation-token field records whether selected words occur in the same package record.

Candidate summaries combine their package comparisons: any V yields V; otherwise all C yields C, and the remaining profiles yield U. Candidates without package evidence are U. We retain package-level outcomes and compare alternative aggregation rules to assess dependence on this summary choice. Selected EMA documents, EDQM terminology [51–59], 101 stratified package comparisons and eight Swiss–EU boundary cases supply documentary checks (S4–S8). SHACL and independent reconstruction check the admitted fields and links [24, 60].

### Source replacement and evidence requests

Stable authorization–tariff keys identify candidates added, removed or shared between D0 and D1. For shared candidates, we compare judgments, supporting records and the next evidence request. This request is a deterministic category for the next inspection step, selected in prerequisite order: obtain missing package context; review a finer-policy conflict; obtain an explicit route; obtain missing formulation wording; otherwise retain supported context. The underlying judgments and records remain available alongside the selected category.

We compare three nested monitoring sets: membership changes alone, membership plus judgment changes, and both plus changes in the next request. This tests whether an update can alter the next review step while leaving the candidate present and its judgment U. Before/after records explain the transitions. S4 and the control archive retain independently reconstructed Retsevmo and Bortezomib examples with their source coordinates.

### Execution measurements and transfer design

Tariff execution compares Neo4j and SQLite using two ways to derive classification–tariff connections. Query-time derivation finds them when a request runs; stored derivation computes and reuses them. Stored links require invalidation and reconstruction after replacement, while both strategies retain the original source premises. Seven tasks retrieve candidates, provenance, rules, combined context, tariff peers with indication information, routes and refreshed records. Combined context returns direct and package-linked classifications with tariff, source and rule identifiers. The tariff-peer query finds products linked to the same tariff and summarizes indication/source evidence. Table 2 separates these implementation contrasts from interventions that change the available information.

Table 2. Controlled contrasts separating information content from execution cost. Source and rule interventions vary analytical inputs; implementation comparisons preserve all requested fields and supporting records.

| Comparison | Analytical target | Controlled contrast |
| --- | --- | --- |
| Source linkage | Additional candidate coverage and its attribution to classification paths | Linking-rule ablation with fixed product identity and package evidence |
| Route specificity | Broad agreement, exact-route conflicts and missing specificity | Coarse and exact-route policies on fixed candidates; separate lexical audit in S4 |
| Source-state comparison | Changes in membership, judgments and evidence requests | Nested monitoring sets over stable product–tariff keys |
| Derivation strategy | Database costs separated from precomputation | Complete-answer comparison of Neo4j and SQLite with query-time and stored links |
| Query formulation | Execution differences between equivalent queries | Plan and formulation contrasts at fixed inputs, indexes and answer content |
| Source replacement | Updated-answer correctness and workload-dependent upkeep | Seven replacement cycles with freshness checks and construction, upkeep and retrieval measurements |
| Task transfer | Reuse under a different interpretation rule | Three-engine comparison across two corpora, hierarchy depths and real-entity subsets, with complete-answer checks and source ablation |

The original component measurements use Linux, Python 3.12.3, SQLite 3.45.1 and Neo4j Community 5.26.1 on a Xeon Silver 4416+ host with 80 reported logical CPUs and approximately 1.08 TB RAM. Neo4j has a 1–2 GiB heap and 1 GiB page cache; SQLite initially uses default connection settings. Three warmups precede fifteen randomized interleaved retrieval repetitions per condition. Timing starts before a local HTTP request and ends after complete decoding; output checking is outside the timer. Seven cycles separately measure loading, materialization, invalidation, replacement and reconstruction. Loading includes each implementation's insertion interface: committed local inserts for SQLite and batched HTTP for Neo4j. S4 records the full environment, indexes, constraints, ANALYZE, cache handling and queries. Equivalent SQL join-order and global/anchor-started recursion controls examine query formulation [61, 62].

The component model estimates serial processing time for a specified workload. With initial build cost B, per-replacement cost R, Q requests, U replacements and context fraction p, C = B + U × R + Q × [p × T_context + (1 − p) × T_peer]. Materialization enters B and upkeep enters R for stored variants; T_peer denotes tariff-peer/indication retrieval. The 600-scenario grid varies request/update counts and task shares as planning assumptions, using warmed retrieval medians. Component-quartile and independent ±10% bounds describe deterministic sensitivity to these inputs (S9). Zero-replacement scenarios use D0 loading as a proxy, and repeated replacements use fixed unit costs.

Two further checks address limits of that calculation. Twenty-eight directly timed build–replacement–100-request cycles measure complete workflows, alongside a separate cache-capacity experiment (S10). Reanalysis separates individual-phase medians, combination of phase/query blocks, pooled-single-query extrapolation and timer residual. S11 also reconciles component changes between the original projections and the later measurements.

A randomized retrieval experiment separately compares services under equal 4 and 8 GiB memory ceilings, no swap, a two-CPU quota and affinity to CPUs 20–21. SQLite default/1 GiB-cache conditions and Neo4j conditions are interleaved within six balanced blocks. Each condition has three warmups and fifteen repetitions per block. Limits, thread affinities, usage and memory events are checked; the client uses other CPUs. Enforced ceilings and actual memory use are recorded separately. A three-pair zero/30-warmup contrast then tests 100 context requests per arm after replacement (S11). These later observations remain separate from the original projection inputs.

The ATC hierarchy task examines a different retrieval question: which products or molecules share an admitted code or ancestor? Starting codes must be seven-character entries in the ATC dictionary; each side permits zero, two or four parent steps. Independent SQL projections and Python traversal check memberships and source ablations across 5,678 Swiss authorizations and 3,647 ChEMBL molecules. Native retrieval compares Neo4j, SQLite and PostgreSQL 16.13 on three nested real-entity sizes, querying fourteen fixed starting entities (anchors) together as one batch. Both SQL engines test whole-hierarchy and anchor-started recursion. Two warmups and nine interleaved repetitions produce 810 batch outputs; PostgreSQL uses 1 GB shared buffers and 64 MB work memory. This changes source populations within ATC, with the hierarchy held constant. Curation reversal, aggregation and workload-coverage analyses are exploratory; S4–S11 retain protocols and secondary analyses.

## Results

### Candidate coverage and route judgments

The curated D0 sources produce 560 candidates through direct SAI classification and four more through authorization-linked SL classification (Table 3). Together, the 564 product–tariff pairs involve 468 authorizations and 179 tariff records, with 1,559 supporting classification paths (Table A2). They comprise 535 ZE, 26 TZE and three RZE pairs. The larger path count reflects multiple explanations for a candidate, while one authorization can also reach several definitions. Neo4j and SQLite reproduce the same pairs and explanations.

Tabrecta shows how the package source adds information. Its recorded SAI code, L01EX17, has no direct tariff match, but authorization 67648 links it to SL packages with L01EP01, matching ZE-2026-225. WHO records the corresponding code alteration in 2026 [63]. The package classification supplies the candidate link; the separately recorded oral route supports compatibility under both route policies. Discovery and route interpretation thus use distinct fields in the same assessment.

Table 3. D0 candidates discovered through SL classification but absent from direct SAI matching. Codes and alteration years describe the frozen sources and recorded WHO context.

| Product; authorization | SAI code | SL/tariff code | Frozen tariff | WHO alteration year |
| --- | --- | --- | --- | --- |
| Irinotecan Fresenius; 61246 | L01XX19 | L01CE02 | ZE-2026-278 | 2021 |
| Irinotecan Labatec; 59284 | L01XX19 | L01CE02 | ZE-2026-278 | 2021 |
| Tabrecta; 67648 | L01EX17 | L01EP01 | ZE-2026-225 | 2026 |
| Votrient; 60326 | L01XE11 | L01EX03 | ZE-2026-140 | 2021 |

Route assessment distinguishes the four additional candidates further. Votrient, like Tabrecta, is compatible under both policies. The two irinotecan descriptions contain infusion wording but no admitted explicit IV token, leaving their exact-route judgments U. Across the full population, 837 linked packages generate 999 package–tariff comparisons because a package may match more than one definition; another 137 candidates have no package evidence. Applying the two route policies to this fixed population changes interpretation while preserving candidate membership (Table 4).

Table 4. Primary route assessments for the same D0 population. V, C and U mean compatible, conflicting and undetermined under the specified rule. Candidate summaries combine package comparisons as defined in Section 3.2. The ancillary formulation-token audit is in S4.

| Policy | Package–tariff paths V / C / U (n=999) | Candidates V / C / U (n=564) |
| --- | --- | --- |
| Coarse family | 913 / 84 / 2 | 388 / 37 / 139 |
| Exact recorded code | 292 / 84 / 623 | 102 / 36 / 426 |

The exact policy exposes six SC–IV discrepancies across five authorizations that coarse grouping treats as compatible: the Entyvio pen and syringe, two Rybrevant SC strengths, Ocrevus subcutaneous and Darzalex SC. Their recorded routes indicate SC, whereas the code-matched tariff definitions require IV. Yet the conflict total remains 84, because six other coarse conflicts become U. Figure 2 therefore shows a change in the identities of conflicting records that the marginal totals conceal. A further 615 coarse-compatible comparisons become undetermined when the fields provide insufficient exact-route specificity. At candidate level, the 388 coarse-compatible summaries become 102 V, five C and 281 U.

**Figure 2. Route transitions at two assessment units.** Panel (a) contains all 999 D0 package–tariff comparisons; panel (b) contains all 564 candidate summaries, including 137 without package evidence. Rows are coarse and columns exact-route outcomes. Highlighted cells show six package comparisons and five candidate summaries changing from compatible to conflicting. Table 4 gives the margins.

Agreement between classification sources does not supply the missing route evidence. Of 423 candidates with both classification paths, only 100 remain compatible under both route policies (Figure 3; Table A4). Tabrecta and Votrient account for the two SL-only candidates with compatible exact-route evidence; all 137 SAI-only candidates lack package context. With package evidence held fixed, removing SL classification removes four candidates and removing direct SAI classification removes 137. For candidates with packages, all contributing comparisons have the same outcome under a given policy in each source state. The three tested aggregation rules therefore yield identical summaries in this population (S4/S5).

**Figure 3. Classification sources and primary route agreement.** Bars group all 564 D0 candidates by classification support. Stable support/conflict means the same outcome under coarse and exact-route comparison; policy-sensitive candidates change outcome. Percentages use each stratum's denominator. All 137 SAI-only candidates lack package-route context. The four SL-only candidates display counts explicitly; Table A4 gives exact totals.

The documentary checks assess agreement with selected external records. The dated official lists contain all sampled authorization and pack keys, and recorded routes agree in the eight selected Swiss–EU comparisons. These findings concern the sampled identities and presentations; Appendix A.4 gives the reference dates, denominators and matching conditions needed to interpret that concordance.

### Source-dependent changes in review evidence

Replacing SAI and SL yields 575 D1 candidates: 545 ZE, 27 TZE and three RZE pairs. Fifteen keys are added, four removed and 560 shared with D0. Among the shared candidates, ten change judgments and twelve change their next evidence request. Of the twelve, ten gain package context but still need an explicit route, one gains compatible route evidence and one loses package context. All four engine/derivation variants reproduce the updated explanations and judgments through seven replacement cycles (S4).

The nested monitoring sets distinguish these effects. Membership changes flag 19 keys; adding judgment changes brings the total to 29. Adding changed evidence requests reaches 31 among the 579 distinct keys present in either state. Every judgment-changing candidate also changes its request, but two further candidates change requests alone. Flixabi (70087) and Eltrombopag Devatis (70153) retain U judgments, including the ancillary field, while new package links move the next unresolved prerequisite from package context to explicit route documentation. Their unchanged judgments therefore conceal a change in what evidence should be sought next.

Retsevmo and Bortezomib illustrate transitions that also change a judgment. Retsevmo tablets (70214) gain SL records documenting oral administration, making the existing ZE-2026-263 candidate compatible under both route policies and retaining supported context. Bortezomib Zentiva (68344) loses its package records, changing from coarse compatibility to U and prompting renewed package-evidence retrieval. In both cases the candidate persists, while the evidence available to interpret it changes.

Earlier curation affects a different comparison: which source is credited with finding a candidate. Reversing the audited SAI edits preserves the complete candidate set but changes its attribution (Table 5). In D0, direct matches fall from 560 to 557 and SL-only candidates rise from four to seven; authorizations 65920, 66495 and 67278 retain SL support after losing direct support. Reversing six XML-discordant D1 fields likewise preserves all 575 candidates and shared route judgments, with 569 direct and six SL-only candidates. The intervention locates the effect in the staged classification fields rather than in database representation.

Table 5. Candidate coverage when the audited SAI code overrides are reversed. Only audited ATC edits are reversed; SL and tariffs remain fixed. Candidate membership and shared route judgments are unchanged in each comparison. D0 raw values come from archived attribution certificates; D1 raw values are checked against XML.

| Source state and SAI view | Direct candidates | SL-only candidates | Complete candidates |
| --- | --- | --- | --- |
| D0 curated staging | 560 | 4 | 564 |
| D0 seven ATC edits reversed | 557 | 7 | 564 |
| D1 curated staging | 571 | 4 | 575 |
| D1 six ATC edits reversed | 569 | 6 | 575 |

Changing request priorities leaves the twelve request-changing shared keys detectable in all six tested orders, although it can change which request is selected. This stability concerns the alert set, not equivalence of the priority rules. Identifier perturbations test a separate dependency: reassignment to an existing authorization adds connections in 1,686 of 1,690 trials, whereas guarded information removal adds none. These stress controls demonstrate the join rule's sensitivity to identifier assignment and the importance of checking identifiers before linkage (S4).

### Tariff-review execution costs

Across 840 retrieval outputs, the four variants agree with the reference keys, explanations and route judgments, including the updated reference after each of seven replacements. Timing comparisons therefore concern implementations returning the same requested evidence. Within Neo4j, storing connections accelerates all five primary retrieval tasks. Median savings recover materialization and upkeep costs after one to four requests, depending on task; the paired-bootstrap 95% interval for combined context is two to three requests. These thresholds compare derivation strategies within Neo4j, before the separate comparison with SQLite.

The cross-engine comparison changes substantially with SQL execution strategy (Table 6). Automatic plans make SQLite combined-context retrieval much slower than Neo4j; fixing join order brings SQLite close to stored Neo4j with the complete answer unchanged. Retrieval alone nevertheless omits the costs of building and replacing the source layer. The workload calculations combine these components to examine how the number and mixture of requests affect total serial processing time.

Table 6. Tariff-review processing-time components, median [Q1–Q3] in milliseconds. QT means query-time derivation and S stored derivation. Maintenance uses seven cycles; retrieval uses fifteen interleaved repetitions. The plan-control rows belong to a separate exploratory run. A zero denotes an omitted phase. The last row projects serial processing time in seconds from the measured components.

| Component | SQLite QT | SQLite S | Neo4j QT | Neo4j S |
| --- | --- | --- | --- | --- |
| Initial load | 647.4 [579.8–700.9] | 647.4 [579.8–700.9] | 5158.8 [4901.8–6000.3] | 5158.8 [4901.8–6000.3] |
| Initial materialization | 0 | 7.6 [7.4–8.4] | 0 | 109.8 [95.5–139.5] |
| Source replacement | 779.1 [696.9–789.6] | 779.1 [696.9–789.6] | 8076.8 [7754.7–8941.8] | 8076.8 [7754.7–8941.8] |
| Invalidation | 0 | 3.5 [2.9–4.4] | 0 | 35.3 [17.9–81.8] |
| Reconstruction | 0 | 7.1 [6.9–7.5] | 0 | 110.8 [84.8–176.3] |
| Combined context, original automatic plans | 2715.5 [2502.1–2911.9] | 9676.7 [9496.2–10000.0] | 174.8 [159.5–189.0] | 32.8 [31.9–35.4] |
| Combined context, plan control: automatic SQL | 2891.4 [2584.1–2962.5] | 9974.3 [9494.6–10437.6] | 166.5 [147.4–176.5] | 37.0 [32.5–40.6] |
| Combined context, same control: ordered SQL | 38.7 [36.1–43.4] | 42.5 [38.5–46.5] | 166.5 [147.4–176.5] | 37.0 [32.5–40.6] |
| Calculated build + replacement + 100 combined requests (s), ordered SQL | 5.30 | 5.69 | 29.89 | 17.19 |

The calculated scenarios illustrate this dependence (Table 7). For pure combined-context requests, stored Neo4j first has a lower projected cost than ordered query-time SQLite at 2,701 requests without replacement, 7,050 after one replacement and 46,196 after ten. The one-replacement, 10,000-request advantage is only 5.05 s, however: component envelopes overlap, and independent perturbations of about 0.65% can reverse the leading median configurations. Replacing 1% of those requests with tariff-peer/indication requests also reverses the median engine choice. With these measured inputs, stored Neo4j has a lower weighted retrieval cost only above approximately 99.36% context share.

Table 7. Calculated serial costs for selected request/replacement scenarios. Each includes one initial build. Context share is the fraction of combined-context requests; the remainder use the tariff peer/indication query. Costs are the minimum median projections among tested configurations within each engine. Separation denotes nonoverlapping Q1–Q3 component envelopes for the engine minima.

| Replacements / requests / context share | SQLite minimum (s) | Neo4j minimum (s) | Median choice / envelope result |
| --- | --- | --- | --- |
| 1 / 100 / 100% | 5.30 | 17.19 | SQLite / separated |
| 1 / 10,000 / 100% | 388.36 | 383.31 | Neo4j / overlap |
| 1 / 10,000 / 99% | 398.95 | 420.59 | SQLite / overlap |
| 0 / 10,000 / 100% | 387.58 | 375.09 | Neo4j / overlap |
| 10 / 10,000 / 100% | 395.37 | 457.32 | SQLite / overlap |
| 10 / 100,000 / 100% | 3877.80 | 3785.71 | Neo4j / overlap |

These thresholds belong to the fixed-cost model rather than to an observed deployment workload. The expanded grid covers 10–100,000 requests, zero to 1,000 replacements and twelve context shares, with finer sampling near the mixture threshold. High replacement counts stress the fixed-unit-cost assumption. Component-quartile bounds separate SQLite at engine level in 490 cells and leave 110 unresolved; none separates Neo4j. Those counts characterize the assumed 600-scenario grid, not the frequency of real workloads. The separate cycle-query control also preserves answers while changing SQLite join order, showing plan sensitivity for converging classification paths (Appendix A.3; Figure A2).

Direct workflow measurement provides a check on how these projections should be used. The cache-capacity experiment preserves all 720 timed answers, and 28 build–replacement–100-request cycles preserve the updated outputs (S10). The original projections use warmed retrieval components; the later outer timers include bursts immediately after replacement. S11 separates component changes from aggregation choices. In its exact decomposition, pooled-single-request extrapolation contributes most of the largest projection error, whereas individual-phase-median aggregation contributes little. The separate warmup contrast varies across pairs. A measured request block retains the contribution of slow requests that extrapolation from a single-request median can miss.

The randomized resource-controlled comparison examines whether the small context-retrieval difference persists after tuning under equal external limits. All 1,080 answers agree with the reference under 4 and 8 GiB ceilings, no swap, equal CPU quota and common service affinity. At 4 GiB, stored-context medians are 40.13 ms for default SQLite and 38.63 ms for Neo4j. Allowing a 1 GiB SQLite cache lowers its median to 35.19 ms, reversing the ordering; the reversal also occurs at 8 GiB. Randomized interleaving addresses the earlier fixed engine sequence, while actual memory usage and HTTP work remain configuration-specific (S11). These tuned conditions supply their own timing evidence and are kept separate from the historical projection inputs.

### Classification-peer retrieval across source populations

The second task replaces tariff-code matching with a hierarchy question: which entities share an admitted ATC code or ancestor? Python and independently expressed SQL agree on memberships for all 5,678 Swiss authorizations and 3,647 ChEMBL molecules at all three depths. At two parent steps per side, admitting Swiss package classifications adds 4,632 unordered peer pairs and expands 1,130 neighborhoods, although only 70 authorizations gain a starting code. A pairwise query explains this wider effect: adding a code to one entity can also change the neighbors returned for another entity whose own codes are unchanged.

ChEMBL changes the source structure from authorization-linked packages to molecule records with ATC-code arrays. Four of 3,651 ATC-bearing records have no admitted starting code. Among the 3,647 eligible molecules, 559 have multiple codes and 314 span multiple first-level groups; prednisolone (CHEMBL131) has thirteen. At the same depth, retaining all codes rather than one per molecule adds 14,170 unordered pairs and expands 2,204 neighborhoods. These links describe shared classification context for the source-specific molecule identities.

All 810 timed native batch outputs agree with the complete reference explanations. At full-Swiss depth four, the batch contains 18,583 explanations. PostgreSQL's global/anchor-started medians are 9,673.7/160.0 ms, SQLite's 225.3/215.8 ms and Neo4j's 323.7 ms. At full ChEMBL depth four, the corresponding times are 129.8/130.6 ms for PostgreSQL, 182.2/150.4 ms for SQLite and 204.1 ms for Neo4j. The large within-PostgreSQL Swiss contrast holds the answer fixed and changes the recursion strategy; its much smaller ChEMBL contrast shows that the benefit depends on the corpus.

These latencies describe fixed anchor batches, whose coverage is examined by the full population census. At Swiss depth two, the population median is 54 peers and the maximum 328, while the selected anchors span one to 93. At ChEMBL depth four, the population maximum is 1,593 and the anchors reach 831. Explanations are also unevenly distributed within a batch: one anchor contributes 51.0% in the shallow full-Swiss batch, compared with a largest contribution of 20.1% at depth four. S4/S5 retain the distributions and source-bound anchor counts, allowing batch timings to be read alongside the neighborhoods they represent.

## Discussion

### Source dependence of review evidence

The source interventions distinguish three effects that an update summary can otherwise conflate: finding a candidate, interpreting its route evidence and identifying what remains missing. A candidate can persist while its source attribution changes, or a new package can resolve one prerequisite while leaving the route judgment U. The two request-only transitions demonstrate the latter case. Recording the supporting evidence and the next prerequisite makes the update visible without treating an unchanged judgment as unchanged information.

For a hospital pharmacy or tariff-review team, this distinction could organize an auditable queue after a catalogue update. Retsevmo and Bortezomib direct attention to gained or lost package evidence; Flixabi and Eltrombopag redirect inspection toward an explicit route. A reviewer would check the authorization, package and presentation, source version/date and applicable tariff condition. Missing fields prompt targeted retrieval, while conflicting identity or route records require specialist assessment. Any additional document would retain its own provenance before the rule is rerun, keeping the subsequent decision traceable to its evidence.

### Configuration-dependent execution costs

Performance interpretation starts with the same requirement: a faster query must still return the requested evidence. The plan controls meet this requirement while changing execution work, and stored derivation shifts work from repeated retrieval into construction and upkeep. The resulting comparisons address different choices—how to formulate the query, whether to precompute links and which implementation to use. Their value depends on the task and the requests expected between source replacements.

The memory comparison shows that SQLite cache tuning can reverse the stored-context median ordering under equal external budgets. Larger cache_size or mmap_size allowances can reduce repeated page reads [64], but the effect depends on the working set and remaining execution costs. Here, the measured reversal demonstrates why a default configuration is an incomplete basis for local database selection.

The cost calibration separates measured workflows from estimates assembled from components. A complete request block retains slow requests whose contribution can be lost when a single-request median is multiplied by the request count. In the checked cycles, this extrapolation accounts for most of the largest discrepancy; summing individual phase medians contributes much less (S11). Component projections are therefore conditional planning calculations. A timing-based operational choice should therefore be checked against the target workflow, particularly when projected differences are small or sensitive to the request mixture.

Concurrent use adds contention and the need to keep related queries on a consistent source version. SQLite serializes writes while write-ahead logging permits reader snapshots alongside a writer [65]; Neo4j uses read-committed isolation and write locks [66]. For security information and event management (SIEM) feeds or AI-agent requests, the reader/writer mix, connection handling and tail latency would also affect evaluation. A proposed publication protocol would build source records and derived links into a validated, immutable replacement snapshot, activate it through an atomic version pointer and bind each review request to one snapshot. Retaining the previous snapshot would let its existing requests finish on that version. Testing this design would extend the present serial measurements to concurrent service.

### Implications for graph–relational evaluation

The additional insight concerns a change in the review process that membership and judgment-only checks miss. In the two request-only cases, new package evidence makes explicit route documentation the next prerequisite, while the candidate and U judgment persist. Evidence-Carrying Validation already retains evidence for validation and repair [31], and KGI-Bench evaluates integration quality [32]. Our contribution combines these established evaluation concerns for source replacement in this task: interventions identify the responsible records, request monitoring detects the additional transition, and complete-output comparison checks that both implementations preserve its evidence before timing. Table 8 specifies the conditions supporting that interpretation.

Table 8. Conditions for interpreting the local comparison. Complete-output agreement checks the declared analytical result; resource settings, timing boundaries and workload define the performance comparison.

| Component | Required condition | Evidence |
| --- | --- | --- |
| Answer | Keys, fields, provenance and multiplicity fixed | Reference reconstruction |
| Information | Sources or rules varied separately | Curation, route and update contrasts |
| Output agreement | Complete tested outputs agree | Tariff, peer and control checks |
| Execution | Plans and derivation stated | Equivalent query controls |
| Resources | Actual limits and interfaces reported | Historical settings; controlled follow-up |
| Decision | Workload and model scope explicit | Scenarios and direct-cycle calibration |

Transfer has two distinct levels: reuse of the procedure and transfer of a measured result. Another medication system can retain the sequence of scoped identities, versioned sources, local rules, independent reference reconstruction and workload measurement. It must supply its own tariff and regulatory conditions; its candidate counts, route outcomes, latencies and crossover thresholds follow from those inputs. ChEMBL demonstrates procedural reuse across source populations within ATC, changing entity identities and code arrays while retaining the hierarchy.

The ATC hierarchy provides a bounded setting for considering other relationship structures. Greater depth, branching and multiple parents can increase explored paths, intermediate joins and alternative explanations. A transfer must therefore specify how repeated or alternative paths enter the answer before comparing selective graph traversal, indexed SQL recursion or precomputed closure. The present results show the importance of access strategy within ATC; evaluating polyhierarchies, cycles and other degree distributions would require corresponding answer checks and measurements. Table 9 summarizes the more immediate choices supported here.

Table 9. Useful properties and selection considerations for the tested database approaches.

| Approach | Useful properties | Limits for local selection |
| --- | --- | --- |
| SQLite | Embedded operation [67, 68]; indexed evidence-preserving joins; low illustrated serial lifecycle costs | Plan sensitivity; serialized writers; explicit refresh publication |
| Neo4j | Typed links and native paths; reusable stored derivations | Service and upkeep costs; workload-dependent savings; usability benefit unmeasured |
| PostgreSQL | Server-based relational retrieval; selective recursive starts | Peer retrieval only; no tariff lifecycle ranking |

A local choice should consequently begin with the answer to be delivered and the workload it must serve. Catalogue rebuilding requires construction and replacement costs as well as latency; repeated retrieval requires the actual task mixture. The illustrative 1% peer-request substitution changes a projected preference, showing how a measured local mixture can inform selection. Maintainability, service constraints and auditability also require local assessment. Existing relational data can support graph-oriented access through SQL/PGQ or Ontop, while Neosemantics supplies Resource Description Framework (RDF) integration for Neo4j [6, 69, 70], extending the implementation options.

### Scope and limitations

The study assesses consistency with declared rules, documentary concordance in selected official records and processing time for specified implementations. These forms of evidence answer different questions. The curation interventions concern seven D0 and six D1 fields; the formulation filter records selected words. Regulatory sources can share origins, and concordant current package records leave historical presentation continuity unresolved. Clinical and payment assessment additionally requires dose, indication, treatment, date and catalogue-specific conditions. Reviewer usability and effects on operational decisions remain to be evaluated.

The timing evidence describes warmed serial retrieval and the stated lifecycle horizons. Equal external ceilings and randomized order strengthen the controlled comparisons; actual memory use, native loading and HTTP work still belong to the measured configurations. Repetitions characterize those deployments, and projections assume fixed components. Concurrent service, cold caches, independent deployments and classifications outside ATC are further empirical settings, rather than established extensions of the reported timing results.

## Conclusions

Medication–tariff review requires a candidate link and source evidence with which to interpret it. In these data, curation changes source-attributed coverage without changing the candidate set, while source replacement changes next evidence requests that judgment-only monitoring misses. Retaining the records and unresolved prerequisite allows both graph and relational implementations to expose those transitions.

Their execution comparison then concerns the cost of returning that same evidence. Query formulation, precomputation, tuning and update/request workload shape the observed and calculated times. Equal-budget controls demonstrate a cache-dependent reversal of the stored-context median ordering, and directly timed cycles show why complete workflows matter alongside component projections. Concurrent services additionally require evaluation of reader/writer contention and a publication protocol aligning source records with derived links. Database selection can build on these checks by measuring construction, refresh and retrieval for the required local workflow.

## Supplementary Materials

S1–S11 are sections of one compact Supplementary Materials document. S1 covers computational checks, S2 identity sensitivity and S3 derivation rules. S4 specifies interpretation, source updates and execution; S5 describes the curation, aggregation and workload analyses. S6–S8 cover catalogue provenance, official-reference comparisons and ancillary extraction checks.

S9 distinguishes conditional cost calculations from observations. S10 reports the initial cache and directly timed lifecycle controls; S11 gives randomized equal-budget retrieval and the exact cost decomposition. Supplementary_Data.zip supplies an evidence index, complete detailed documents and the original code/result archives, including Decision_Analysis.zip. It retains full tables, queries, source coordinates, protocols, raw measurements and verification code.

## Author Contributions

Christian Franke: software, integration-system design and implementation. Murat Sariyar: software and investigation, including matched database evaluations, source-replacement analyses, classification-peer retrieval and reproducibility.

## Funding

This research was supported by the Swiss National Science Foundation under grant number 211751.

## Institutional Review Board Statement

Not applicable. The study analyzes public medication, classification and administrative source records and includes no patient-level data or newly recruited participants.

## Informed Consent Statement

Not applicable. No individual patient records or participant data are analyzed.

## Data Availability Statement

The base reproduction package is archived as v1.0.0 at https://doi.org/10.5281/zenodo.23646927, with source revision https://github.com/sym33/graph-sql/tree/fac0a0290155b952a7e44cd73371cfcc6cd27ee5. It supplies the study code, frozen inputs, reference documents, protocols and measurements. Original study software is MIT-licensed; third-party material retains its respective rights.

The current revision and Supplementary_Data.zip are available at https://github.com/sym33/graph-sql/tree/main/revisions/2026-11-20. Supplementary_Data.zip extends the base with exploratory analyses, official-reference comparisons, ancillary procedures, calculated scenarios and subsequent execution controls. The compact supplementary document explains the corresponding rules and results in sections S1–S11. Offline replay reconstructs or verifies saved analytical results; database latency is remeasured only by running the native experiments. URLs, versions, source locators and hashes identify the evaluated snapshots. Full product-information documents retrieved for S6–S7 are not redistributed.

## Acknowledgments

The authors acknowledge the public data providers. **Generative AI Disclosure:** During manuscript preparation, the authors used OpenAI ChatGPT and Anthropic Claude for structural critique, drafting support, language editing, analysis-code assistance and automated consistency checks. The authors reviewed and revised the AI-assisted material, verified the cited sources and take full responsibility for the final content. Supplement S8 describes ancillary documentary extraction and model-family checks.

## Conflicts of Interest

Christian Franke is employed by SwissDRG AG, whose public tariff material is used in the study. The authors declare no conflicts of interest.

## Appendix A. Supporting evidence and additional analyses

This appendix provides the source records, denominators and reference scopes underlying the main comparisons. It separates candidates from their supporting paths, examines classification and presentation evidence, and documents the database configurations and transfer boundaries. Optional evidence-acquisition rules and calculations remain in S4.

### Evaluation design and source dependence

The counting unit determines what a source comparison can establish. Several records may support one candidate, and several candidates may involve one authorization; paths, candidate pairs and classification sets consequently have different denominators. Evidence-carrying validation [31], mutation testing and integration benchmarks [32, 71], and provenance/claim-verification systems [72, 73] motivate checking conclusions with their supporting records. Ontop [69] and provenance-aware ontology-based access [23] likewise support explanations grounded in source data. Table A1 relates these established techniques to the specific contrasts used here.

Table A1. Methodological contrasts and evaluation targets.

| Comparison question | Established foundation | Evaluation target |
| --- | --- | --- |
| What does an additional source path contribute? | Identifier integration and provenance [21–23] | Candidate-key gains and source dependence, separated from implementation timing |
| What does a more specific interpretation contribute? | Typed integration and executable constraints [20, 24, 25] | Complete route transitions and source-bound next-step categories |
| Can two models deliver the same complete answer? | Matched relational–graph benchmarking [4, 9] | Identifiers, fields, supporting records and repeated rows checked across both derivation strategies |
| When does storing derivations recover its cost? | Native adjacency and indexed querying [9, 74] | Within-system retrieval and materialization contrasts with lifecycle break-even estimates |
| Is the timing difference explained by a plan? | Query-plan inspection [61, 75, 76] | Predicate-preserving intervention with complete answer checks |
| Does the comparison survive source replacement? | Provenance and data-quality obligations [21, 22, 26, 31] | Reconstructed updated answers, zero stale outputs and separately timed upkeep |

Table A2 distinguishes the D0 populations: 1,559 source-linked paths support 564 product–tariff candidates. Historical derivations, broader classifications and European references have separate interpretation rules and are counted separately from the admitted Swiss documentary candidates. Admission of a European connection to that set would require the relevant Swiss identity bridge; a missing bridge withholds the connection rather than demonstrating that no real-world match exists.

Table A2. Complete D0 inference populations and contextual selection.

| Quantity | Count | Interpretation |
| --- | --- | --- |
| Documentary source-record–tariff linking paths | 1,559 | Source-linked Swiss classification paths |
| Distinct product–tariff-record pairs | 564 | Catalogue candidates with retained explanations |
| Swiss authorizations represented | 468 | Authority-scoped references |
| Tariff definitions reached | 179 | 176 SwissDRG ZE, two TARPSY TZE and one ST Reha RZE; source/version identities retained |
| Additional pairs through SL | 4 | Absent from direct SAI joins |
| Historical derivations | 5 | Separate historical review target |
| Historical-only Swiss products | 2 | No documentary candidate in this catalogue |
| European-reference derivations withheld | 324 | Missing Swiss identity bridge |
| Recorded broader-group derivations | 5,204 | Witness-level dictionary generalization |
| Package-record–tariff pairs | 999 | Comparisons retaining the recorded ingredient descriptions |

Before applying the tariff rule, classification-source comparison asks whether SAI and SL record the same code (Table A3). Of 3,467 D0 authorizations present in both sources, 78 differ: 30 have prefix-hierarchical differences, 22 are connected by the specified temporal-or-hierarchical rule and 26 remain unreconciled. Differences affect six authorizations at the first ATC level, 14 at prefix length three, 26 at four and 48 at five. These nested counts show how discrepancies increase at finer code levels. Thyrogen (H01AB01 in Refdata, V04CJ01 in SL) and UROCIT (G04BC and A12BA02) illustrate that source choice can also alter broad classification cohorts.

Table A3. Complete classification-source views across dated inputs.

| Quantity | Comparison extract | D0 |
| --- | --- | --- |
| Authorizations with recorded classifications | 6,302 | 6,322 |
| Represented in one source | 2,833 | 2,855 |
| Exact agreement between both sources | 3,379 | 3,389 |
| Prefix-hierarchical difference | 40 | 30 |
| Recorded temporal or hierarchical difference | 24 | 22 |
| Unreconciled difference under specified relations | 26 | 26 |
| All recorded product–code pairs | 6,392 | 6,400 |
| Product–code pairs in exact-agreement view | 3,379 | 3,389 |

The route comparison adds a separate dimension to classification agreement. Table A4 shows that matching SAI and SL classifications can still yield different outcomes under coarse and exact-route policies. Among the four SL-only candidates, two remain compatible under both policies and two depend on route resolution; all 137 SAI-only candidates lack linked package evidence in the review output. Independent SQL reconstruction and physical graph extraction reproduce these classification-source and route groups.

Table A4. Classification-source profiles under the two primary route policies for all 564 D0 candidates. Stable outcomes agree between coarse and exact-route comparison.

| Classification support | Stable support | Stable conflict | Policy-sensitive | Undetermined throughout |
| --- | --- | --- | --- | --- |
| Both SAI and SL | 100 | 31 | 290 | 2 |
| SAI only | 0 | 0 | 0 | 137 |
| SL only | 2 | 0 | 2 | 0 |
| Total | 102 | 31 | 292 | 139 |

### Classification-reference coverage

Comparing a recorded classification with an external reference first requires resolving the entity being compared. EMA substance names are matched to ChEMBL 37 preferred names and then synonyms [46], accepting a match only when it identifies one parent substance. The ATC value being checked is excluded from identity selection, so code agreement cannot itself determine the reference. Code assessment then distinguishes exact support, hierarchical compatibility and named WHO alterations [63]. Official product information and WHO entries provide checks for five remaining discrepancies [77–83]. Classification dates are kept separate from document update and retrieval dates.

Table A5. External-reference outcomes under two assessment units.

| Outcome | EMA medicine rows | Unique substance–ATC combinations |
| --- | --- | --- |
| Exact external support | 883 | 523 |
| Hierarchical compatibility | 68 | 66 |
| Named temporal compatibility | 43 | 38 |
| Discordant | 5 | 5 |
| Malformed or partially supported | 3 | 2 |
| Unresolved or missing code | 567 | 474 |
| Total assessed | 1,569 | 1,108 |

Identity resolution succeeds for 1,013 of 1,569 EMA rows, using 955 preferred-name and 58 synonym matches. Of the resolved rows, 994 have exact, hierarchical or temporal code compatibility. The 556 unresolved identities comprise 358 unmatched names, 195 multicomponent entries and three missing substance fields. Table A5 also accounts for missing or unresolved classifications after identity selection, so its code-assessment categories differ from identity-resolution counts. Supported classifications cover 63.35% of medicine rows and 56.59% of 1,108 unique substance–ATC combinations. The two percentages describe different assessment units.

The Refdata overrides introduce a temporal issue as well as a coverage issue. Of 22 configured changes, seven alter a D0 field and six alter a D1 field in the XML comparison; Table 5 gives their candidate-coverage effects, and attribution records retain raw and curated values. Determining which code is currently authorized requires a dated product-specific source. For four medicines, EMA metadata and product information contain different ATC values, but the dates when those values became applicable could not be established. S2 records identity-policy sensitivities and these source-specific boundaries.

### Presentation-specific route evidence

The complete frozen L04AC07 cohort contains five medicines [84–88] and tests whether shared classification also implies the same documented routes. Extracted evidence retains the product-information document, page, formulation title and passage, yielding eight medicine–route relationships. For each route listed for one medicine, the comparison checks its inclusion in each of the other four medicines' inventories. A route is counted as absent only when the target inventory is complete under the extraction rule; an unavailable inventory yields U. The relational implementation reconstructs the same source facts as the graph representation.

Table A6. Complete external-reference transfer cohort and documented route inventories.

| EMA medicine | Complete label fields | Documented routes | ATC agreement with product information |
| --- | --- | --- | --- |
| RoActemra | 5 | IV, SC | L04AC07 |
| Tuyory | 2 | SC | L04AC07 |
| Tocilizumab STADA | 3 | IV | L04AC07 |
| Avtozma | 9 | IV, SC | L04AC07 |
| Tyenne | 3 | IV, SC | L04AC07 |
| Total | 22 | 8 medicine–route relationships | 5/5 |

The 22 label fields produce 32 directed comparisons. Coarse parenteral grouping supports all 32, whereas exact assessment supports 24 and identifies eight cases of inventory noncoverage: four for SC absent from Tocilizumab STADA and four for IV absent from Tuyory. These are dependent comparisons reusing two missing target routes. With target inventories withheld, every comparison becomes undetermined. SQL and native Cypher agree on all keys and judgments. Frozen D0 ATC metadata define the cohort, while official product information supplies its separate route reference.

The downstream package query tests whether derived links retain enough evidence for a further assessment. Grouping all 999 package–tariff links by exact recorded ingredient-description text and tariff produces 172 groups across 146 descriptions. Exact-route assessment selects two groups containing both compatible and conflicting outcomes, both labeled “voriconazolum”. Their 17 packages across 12 authorizations contain 12 oral, one explicit-IV and four generic-parenteral recordings. The oral tariff yields a 12/1/4 compatible/conflicting/undetermined profile; the IV tariff reverses the first two counts (Figure A1). Coarse grouping selects eight mixed groups; exact assessment and the ancillary token audit each select two (S4).

Selected EMA labels provide formulation context for this example. Five Vfend packaging fields describe oral routes in four tablet/suspension labels and IV in one infusion label [89]; Swiss package records remain the evidence for Swiss authorizations. Independent SQL reproduces the declaration pairs and policy profiles. Removing derived edges empties the downstream query, and restoring them recovers its result with source records unchanged. This intervention checks that the subsequent query uses the derived connections while preserving their original premises.

**Figure A1. Route profiles for packages sharing the ingredient description “voriconazolum”.** Materialized graph relationships connect records with that ingredient description to two tariff entries. Exact-route assessment distinguishes the same 17 package records as oral, explicit-IV or generic-parenteral, producing opposite support profiles for the two tariffs. Counts describe package records across 12 authorizations.

The cycle query examines another aspect of provenance: whether different paths supply independent evidence. It returns one cycle for Prothromplex (41330), none for authorizations 31096 and 44470, and no result for missing-product controls; Neo4j and SQLite agree throughout. Prothromplex reaches B02BD01 through direct SAI and authorization-linked SL classifications. Both paths reuse the same SAI row, while the latter adds an SL row (Figure A2). Distinct paths therefore expose their shared premise rather than counting as independent corroboration.

Its execution comparison also depends on the timing boundary. Neo4j HTTP medians of 7.3–9.0 ms initially compare with 23.4–42.3 ms for automatically planned SQLite. A separate embedded SQL join-order control returns the same answers in 0.019–0.038 ms. This demonstrates plan sensitivity within SQLite; the embedded interface and separate session keep that control distinct from the cross-engine HTTP comparison.

**Figure A2. A classification cycle and its shared source evidence.** (a) Two classification records connect Prothromplex to B02BD01, forming a cycle when the links are viewed without direction; arrows retain the stored relationship directions. (b) Filled circles identify the source records used by each path. Both reuse the same SAI record; the SL-derived path additionally uses an SL package record. Source identities and relationship directions correspond to the evaluated D1 graph.

### Official-reference and cross-jurisdiction checks

The official-reference sample contains 101 D0 package–tariff comparisons stratified by their outcomes, spanning 74 authorization and 92 distinct pack keys. Swissmedic lists dated 30 September 2026 were retrieved on 26 October 2026 [90]. Authorization and pack-key matching establishes the reference identity before ATC comparison. The assessed authorization fields are frozen SAI staging values, including configured overrides. The comparison distinguishes exact code agreement from hierarchical compatibility.

The Swiss–EU check uses eight deliberately selected boundary cases: two Entyvio devices, two Rybrevant SC strengths, Ocrevus SC, Darzalex SC, the Actemra/RoActemra pen comparison and Luxturna [53–56, 84, 91]. Ingredient, strength and formulation/device define the comparison while preserving national identities. Locators and document hashes identify the supporting passages. These records assess concordance for the selected presentations; shared regulatory or sponsor origins limit reference independence, and agreement at the retrieved dates leaves historical continuity and full formulation equivalence unresolved. S8 describes extraction assistance.

All 182 ZE signatures agree with both official catalogue releases on ATC, route, dose unit and qualifier. The Swissmedic reference lists contain all 74 sampled authorization keys and all 92 pack keys. Frozen SAI staging ATC agrees exactly for 73 of 74 keys; Spinraza has M09AX07 in staging and the broader M09AX in the reference. SL agrees exactly in 100 of 101 comparison rows, with the same hierarchical difference. Only seven authorization names match after normalization, because official names often add strength or formulation details; authorization and pack keys anchor these comparisons. Routes also agree in the eight selected Swiss–EU cases across six EMA documents. Table A7 separates their denominators and reference scopes.

Table A7. Exploratory concordance with dated reference records. The Swiss sample contains 101 comparison rows, 74 authorization keys and 92 distinct pack keys. Identifier presence, code agreement and route concordance have their respective denominators; historical continuity and payment entitlement require further evidence.

| Reference check | Denominator | Result and boundary |
| --- | --- | --- |
| Swissmedic authorization-key presence | 74 authorization keys | 74 found; seven names equal after normalization; names can differ by strength/formulation detail |
| Swissmedic pack-key presence | 92 distinct pack keys | 92 found, covering all 101 comparison rows; historical pack continuity unproven |
| Frozen SAI staging ATC | 74 authorization keys | 73 exact; one coarser current code, M09AX versus frozen M09AX07 |
| Recorded SL ATC | 101 comparison rows | 100 exact; one comparison has the same hierarchical difference |
| Swiss–EU route concordance | Eight selected cases; six EMA documents | Eight agree after ingredient/strength/formulation matching; national identities stay separate |

### Configuration and transfer boundaries

The original cost model uses the deployment settings summarized in Table A8. Later S11 controls address external resource ceilings and engine order separately; they do not replace the original model's measurements or native loading interfaces. Table A9 distinguishes the measured components of the two tasks: tariff review includes SQLite/Neo4j build–replacement lifecycles, while the classification hierarchy task compares retrieval in three engines.

Table A8. Original configuration asymmetries. The cache-capacity and resource-controlled retrieval checks are reported separately in S10–S11. S4 provides the full original interface and memory settings.

| Dimension | SQLite | Neo4j | PostgreSQL |
| --- | --- | --- | --- |
| Version and deployment | 3.45.1; file-backed, embedded engine | Community 5.26.1; server | 16.13; server |
| Timed retrieval interface | Local HTTP Python bridge; sqlite3 | Transactional HTTP endpoint | Local HTTP Python bridge; psycopg2 |
| Memory settings | Default connection settings; no matched engine memory cap | Heap 1–2 GiB; page cache 1 GiB | Shared buffers 1 GB; work memory 64 MB |
| Access controls | Entity/code indexes; hierarchy directions indexed | Unique witness/code keys and entity lookup index | Entity/code/hierarchy indexes; ANALYZE after loading |
| Tariff loading/replacement | Committed local inserts | Parameterized HTTP batches | Not measured |
| Evaluated task scope | Tariff lifecycle and peer retrieval | Tariff lifecycle and peer retrieval | Peer retrieval only |

Table A9. Evaluation steps in the original two-task comparison. Later execution controls are reported in S10–S11. The columns identify the components measured for each task.

| Step | Medication–tariff review | Classification-peer retrieval |
| --- | --- | --- |
| Answer contract | Candidate, route judgment, source premises and package multiplicities | Two entities, codes, witnesses, source records, ancestor and depths |
| Complete-output agreement | Reference checks and 840 four-variant outputs | Census checks and 810 repeated batch outputs |
| Information effects | Linking-path ablation, ATC edits, route policies and source replacement | Swiss package-code ablation, ChEMBL code reduction and hierarchy depth |
| Workload | Seven retrieval tasks; seven replacement cycles | Two corpora, three real-entity subset sizes, three depths; fourteen fixed anchors |
| Execution alternatives | Query-time/stored derivation and SQL join-order controls | Three engines; global/anchor-started SQL recursion; no corresponding materialization factorial |
| Local choice | Serial lifecycle projection for measured SQLite/Neo4j configurations | Retrieval-only comparison; no PostgreSQL lifecycle conclusion |

## References

1. Podchiyska T, Hernandez P, Ferris T, Weber S, Lowe HJ. Managing Medical Vocabulary Updates in a Clinical Data Warehouse: An RxNorm Case Study. AMIA Annual Symposium Proceedings. 2010;2010:477–481. https://pubmed.ncbi.nlm.nih.gov/21347024/.

2. Lester CA, Flynn AJ, Marshall VD, Rochowiak S, Rowell B, Bagian JP. Comparing the variability of ingredient, strength, and dose form information from electronic prescriptions with RxNorm drug product descriptions. Journal of the American Medical Informatics Association. 2022;29(9):1471–1479. https://doi.org/10.1093/jamia/ocac096.

3. Triep K, Endrich O. Callenging Interoperability: Mapping and Validation of a Swiss Medication Catalogue to RxNorm. Stud Health Technol Inform. 2026;336:1822–1824. https://doi.org/10.3233/SHTI260550.

4. Cheng Y, Ding P, Wang T, Lu W, Du X. Which Category Is Better: Benchmarking Relational and Graph Database Management Systems. Data Sci Eng. 2019;4:309–322. https://doi.org/10.1007/s41019-019-00110-3

5. Jin G, Salihoğlu S. Making RDBMSs Efficient on Graph Workloads Through Predefined Joins. arXiv. 2021;2108.10540. https://doi.org/10.48550/arXiv.2108.10540

6. ten Wolde D, Szárnyas G, Boncz P. DuckPGQ: Bringing SQL/PGQ to DuckDB. Proc VLDB Endow. 2023;16(12):4034–4037. https://doi.org/10.14778/3611540.3611614

7. Rotschield H, Peterfreund L. Towards Cross-Model Efficiency in SQL/PGQ. Proceedings of GRADES-NDA. 2025. https://doi.org/10.1145/3735546.3735860

8. Franke C, Sariyar M. Modeling Reimbursement-Relevant Drug Data as a Property Graph. Stud Health Technol Inform. 2026;338:616–620. https://doi.org/10.3233/SHTI260918

9. Pacaci A, Zhou A, Lin J, Özsu MT. Do We Need Specialized Graph Databases? Benchmarking Real-Time Social Networking Applications. Proceedings of GRADES. 2017;Article 12:1–7. https://doi.org/10.1145/3078447.3078459

10. Knox C, Wilson M, Klinger CM, et al. DrugBank 6.0: the DrugBank Knowledgebase for 2024. Nucleic Acids Res. 2024;52(D1):D1265–D1275. https://doi.org/10.1093/nar/gkad976

11. Yang J, Zhuang X, Li Z, Xiong G, Xu P, Ling Y, Zhang G. CPMKG: a condition-based knowledge graph for precision medicine. Database (Oxford). 2024;2024:baae102. https://doi.org/10.1093/database/baae102

12. Farrugia L, Azzopardi LM, Debattista J, Abela C. medicX-KG: a knowledge graph for pharmacists’ drug information needs. J Biomed Semantics. 2025;16:11. https://doi.org/10.1186/s13326-025-00332-7

13. Chen C, Amith M, Roberts K, Mauldin R, Komalasari R, Tao C. An application-based ontological knowledge base of medications to support health literacy and adherence for the consumer population: an aging population use case. J Biomed Semantics. 2026;17:4. https://doi.org/10.1186/s13326-026-00347-8

14. Cui H, Zhu X, Zhang W, Piao M, Peng Y. From knowledge silos to integrated insights: building a cardiovascular medication knowledge graph for enhanced medication knowledge retrieval, relationship discovery, and reasoning. Front Cardiovasc Med. 2025;12:1526247. https://doi.org/10.3389/fcvm.2025.1526247

15. Branting LK, Reeder F, Gold J, Champney T. Graph Analytics for Healthcare Fraud Risk Estimation. Proceedings of the 2016 IEEE/ACM International Conference on Advances in Social Networks Analysis and Mining. 2016:845–851. https://doi.org/10.1109/ASONAM.2016.7752336

16. Sun H, Xiao J, Zhu W, He Y, Zhang S, Xu X, Hou L, Li J, Ni Y, Xie G. Medical Knowledge Graph to Enhance Fraud, Waste, and Abuse Detection on Claim Data: Model Development and Performance Evaluation. JMIR Med Inform. 2020;8(7):e17653. https://doi.org/10.2196/17653

17. Callahan TJ, Tripodi IJ, Stefanski AL, et al. An open source knowledge graph ecosystem for the life sciences. Sci Data. 2024;11:363. https://doi.org/10.1038/s41597-024-03171-w

18. Cortes KG, Sundar S, Gehrke S, et al. Improving Biomedical Knowledge Graph Quality: A Community Approach. arXiv preprint. 2025;2508.21774v1. https://doi.org/10.48550/arXiv.2508.21774

19. Hu S, Cheng H, Gillenwater L, et al. Beyond Identifier Matching: An Empirical Characterization of Failure Modes in Biomedical Knowledge Graph Integration. medRxiv preprint. 2026;2026.05.26.26354182v1. https://doi.org/10.64898/2026.05.26.26354182

20. Touré V, Unni D, Krauss P, Marto AB, Kalt K, Stoira N, Pickl M, Österle S. SPHN Connector – a scalable pipeline for generating validated knowledge graphs from federated and semantically enriched health data. BMC Med Inform Decis Mak. 2026;26:72. https://doi.org/10.1186/s12911-026-03383-7

21. Green TJ, Karvounarakis G, Tannen V. Provenance semirings. Proceedings of PODS. 2007:31–40. https://doi.org/10.1145/1265530.1265535

22. Moreau L, Missier P, editors. PROV-DM: The PROV Data Model. W3C Recommendation. 2013. https://www.w3.org/TR/prov-dm/

23. Calvanese D, Lanti D, Ozaki A, Peñaloza R, Xiao G. Enriching Ontology-based Data Access with Provenance. IJCAI. 2019:1616–1623. https://doi.org/10.24963/ijcai.2019/224

24. Knublauch H, Kontokostas D, editors. Shapes Constraint Language (SHACL). W3C Recommendation. 2017. https://www.w3.org/TR/shacl/

25. Knublauch H, Steyskal S, editors. SHACL Advanced Features. W3C Working Group Note. 2017. https://www.w3.org/TR/shacl-af/

26. Mendes PN, Mühleisen H, Bizer C. Sieve: Linked Data Quality Assessment and Fusion. Proceedings of the 2012 Joint EDBT/ICDT Workshops. 2012:116–123. https://doi.org/10.1145/2320765.2320803

27. Ong R, Sun J, Șerban O, Guo Y-K. TKGQA Dataset: Using Question Answering to Guide and Validate the Evolution of Temporal Knowledge Graph. Data. 2023;8(3):61. https://doi.org/10.3390/data8030061.

28. Dibowski H. Full Traceability and Provenance for Knowledge Graphs. In: Formal Ontology in Information Systems (FOIS 2024). Front Artif Intell Appl. 2024;394:223–237. https://doi.org/10.3233/FAIA241309

29. Wei C-P, Tsai P-Y, Li J-J. Biomedical knowledge graph verification with multitask learning architectures. J Biomed Inform. 2025;169:104894. https://doi.org/10.1016/j.jbi.2025.104894

30. Lin X, Ma S, Shan J, Zhang X, Hu SX, Guo T, Li SZ, Yu K. BioKGBench: A Knowledge Graph Checking Benchmark of AI Agent for Biomedical Science. arXiv preprint. 2024;2407.00466v1. https://doi.org/10.48550/arXiv.2407.00466

31. Fierro G. Evidence-Carrying Validation for Knowledge Graphs. arXiv preprint. 2026. arXiv:2608.15948v1, 16 August 2026. https://arxiv.org/abs/2608.15948

32. Hofer M, Rahm E. Evaluation of Pipelines for Data Integration into Knowledge Graphs. arXiv preprint. 2026. https://arxiv.org/abs/2605.22304

33. Monteiro J, Sá F, Bernardino J. Experimental Evaluation of Graph Databases: JanusGraph, Nebula Graph, Neo4j, and TigerGraph. Applied Sciences. 2023;13(9):5770. https://doi.org/10.3390/app13095770.

34. Han X, Tian Y. Storage and Query of Drug Knowledge Graphs Using Distributed Graph Databases: A Case Study. Bioengineering. 2025;12(2):115. https://doi.org/10.3390/bioengineering12020115

35. Qi S, Tong B, Hu J, et al. The LDBC Financial Benchmark: Transaction Workload. Proc VLDB Endow. 2025;18(9):3007–3020. https://doi.org/10.14778/3746405.3746424

36. Liu Z, Huang X, Liu X, Wang S, Peng Z. GRBench: A Comprehensive Benchmark Evaluation for Graph-relational Data Management. arXiv preprint. 2026;2608.31027v1. https://doi.org/10.48550/arXiv.2608.31027 (submitted 31 August 2026; checked 20 November 2026).

37. He Y, Fang R, Dillig I, Wang Y. Graphiti: Bridging Graph and Relational Database Queries. Proc ACM Program Lang. 2025;9(PLDI):Article 216, 1716–1740. https://doi.org/10.1145/3729319

38. Amendola G, Libkin L. Explainable Certain Answers. Proceedings of IJCAI. 2018:1683–1690. https://doi.org/10.24963/ijcai.2018/233

39. Altwaijry H, Kalashnikov DV, Mehrotra S. Query-Driven Approach to Entity Resolution. Proc VLDB Endow. 2013;6(14):1846–1857. https://doi.org/10.14778/2556549.2556567

40. Bergman M, Milo T, Novgorodov S, Tan WC. Query-Oriented Data Cleaning with Oracles. Proceedings of SIGMOD. 2015:1199–1214. https://doi.org/10.1145/2723372.2737786

41. Kanagal B, Li J, Deshpande A. Sensitivity Analysis and Explanations for Robust Query Evaluation in Probabilistic Databases. Proceedings of SIGMOD. 2011:841–852. https://doi.org/10.1145/1989323.1989411

42. teletrabbie. MediGraph source repository, revision ae992d5, 5 June 2026. https://github.com/teletrabbie/medi_graph/tree/ae992d5f3e6333643bb8aaf8a646842dcca04460 (inspected 10 October 2026).

43. Federal Office of Public Health. Elektronische Plattform Leistungen (ePL). Official SL migration and data-publication notice. https://www.bag.admin.ch/de/elektronische-plattform-leistungen-epl (accessed 10 October 2026).

44. Refdata Foundation. SAI structured export, published 5 October 2026. https://sai.refdata.ch/download/structuredexportzip/9029 (acquired 13 October 2026; frozen source digest in the experiment manifest).

45. Federal Office of Public Health. Current and archived Specialities List publications. https://sl.bag.admin.ch/resources/current-and-archived-data (official current Excel export acquired 13 October 2026; frozen source digest in the experiment manifest).

46. EMBL-EBI. ChEMBL Data Web Services; molecule, status and ATC resources. ChEMBL 37, released 1 May 2026; retrieved 10 October 2026. https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services

47. Neo4j. Graph database concepts. Getting Started documentation. https://neo4j.com/docs/getting-started/appendix/graphdb-concepts/ (accessed 17 October 2026).

48. Neo4j. Constraints. Cypher Manual. https://neo4j.com/docs/cypher-manual/current/schema/constraints/ (accessed 17 October 2026).

49. Motik B, Cuenca Grau B, Horrocks I, Wu Z, Fokoue A, Lutz C, editors. OWL 2 Web Ontology Language Profiles, Second Edition. W3C Recommendation. 2012. https://www.w3.org/TR/owl2-profiles/

50. SwissDRG AG. Technisches Begleitblatt – Erfassung hochteurer Medikamente in der Medizinischen Statistik der Krankenhäuser des Bundesamtes für Statistik (BFS) im Jahr 2023. Version 12.0, 23 November 2022, Section 3.1(c), p. 3. https://www.swissdrg.org/application/files/7716/6936/5719/Technisches_Begleitblatt_2023_Aenderungsdokument.pdf (route-code definitions checked 22 October 2026).

51. European Medicines Agency. Cresemba: English EPAR product information, sections 1 and 4.2. https://www.ema.europa.eu/en/documents/product-information/cresemba-epar-product-information_en.pdf (retrieved 10 October 2026).

52. European Medicines Agency. Noxafil: English EPAR product information, sections 1 and 4.2. https://www.ema.europa.eu/en/documents/product-information/noxafil-epar-product-information_en.pdf (retrieved 10 October 2026).

53. European Medicines Agency. Entyvio: English EPAR product information, sections 1 and 4.2. https://www.ema.europa.eu/en/documents/product-information/entyvio-epar-product-information_en.pdf (retrieved 10 and 26 October 2026; snapshot identities in the experiment manifest and Supplement S7).

54. European Medicines Agency. Ocrevus: English EPAR product information, sections 1 and 4.2. https://www.ema.europa.eu/en/documents/product-information/ocrevus-epar-product-information_en.pdf (retrieved 10 and 26 October 2026; snapshot identities in the experiment manifest and Supplement S7).

55. European Medicines Agency. Rybrevant: English EPAR product information, sections 1 and 4.2. https://www.ema.europa.eu/en/documents/product-information/rybrevant-epar-product-information_en.pdf (retrieved 10 and 26 October 2026; snapshot identities in the experiment manifest and Supplement S7).

56. European Medicines Agency. Darzalex: English EPAR product information, sections 1 and 4.2. https://www.ema.europa.eu/en/documents/product-information/darzalex-epar-product-information_en.pdf (retrieved 10 and 26 October 2026; snapshot identities in the experiment manifest and Supplement S7).

57. European Medicines Agency. Tabrecta: English EPAR product information, sections 1 and 4.2. https://www.ema.europa.eu/en/documents/product-information/tabrecta-epar-product-information_en.pdf (retrieved 10 October 2026).

58. European Medicines Agency. Votrient: English EPAR product information, sections 1 and 4.2. https://www.ema.europa.eu/en/documents/product-information/votrient-epar-product-information_en.pdf (retrieved 10 October 2026).

59. HL7 International. International Patient Summary 2.0.1: EDQM route of administration value set, 85-concept published expansion. https://www.hl7.org/fhir/uv/ips/en/ValueSet-medicine-route-of-administration.html (retrieved 10 October 2026).

60. RDFLib contributors. pySHACL: Python implementation of Shapes Constraint Language. Version 0.31.0 used in this study. https://github.com/RDFLib/pySHACL (accessed 10 October 2026).

61. SQLite developers. The SQLite Query Optimizer Overview, Section 7.1.2: Manual Control of Query Plans using CROSS JOIN. https://sqlite.org/optoverview.html (accessed 13 October 2026).

62. PostgreSQL Global Development Group. PostgreSQL 16 Documentation: WITH Queries, Section 7.8. https://www.postgresql.org/docs/16/queries-with.html (accessed 25 October 2026).

63. WHO Collaborating Centre for Drug Statistics Methodology. ATC alterations from 2005–2026. Retrieved 9 October 2026. https://atcddd.fhi.no/atc_ddd_alterations__cumulative/atc_alterations/

64. SQLite contributors. PRAGMA Statements: cache_size and mmap_size. https://www.sqlite.org/pragma.html (accessed 20 November 2026).

65. SQLite contributors. Isolation in SQLite. https://www.sqlite.org/isolation.html (accessed 20 November 2026).

66. Neo4j. Concurrent data access. Operations Manual. https://neo4j.com/docs/operations-manual/current/database-internals/concurrent-data-access/ (accessed 20 November 2026; used for explanatory discussion, not as a record of historical deployment settings).

67. SQLite developers. Appropriate Uses For SQLite. https://www.sqlite.org/whentouse.html (accessed 17 October 2026).

68. SQLite developers. SQLite Is Serverless. https://www.sqlite.org/serverless.html (accessed 17 October 2026).

69. Calvanese D, Cogrel B, Komla-Ebri S, Kontchakov R, Lanti D, Rezk M, Rodriguez-Muro M, Xiao G. Ontop: Answering SPARQL queries over relational databases. Semantic Web. 2017;8:471–487. https://doi.org/10.3233/SW-160217

70. Neo4j Labs. Neosemantics (n10s): Neo4j RDF and Semantics Toolkit. https://neo4j.com/labs/neosemantics/ (accessed 11 October 2026).

71. John T, Johnsen EB, Kamburjan E. Mutation-based testing of knowledge graphs. Empir Softw Eng. 2026;31:99. https://doi.org/10.1007/s10664-026-10810-w

72. Amaral G, Rodrigues O, Simperl E. ProVe: A pipeline for automated provenance verification of knowledge graphs against textual sources. Semantic Web. 2024;15(6):2159–2192. https://doi.org/10.3233/SW-233467

73. Dammu PPS, Naidu H, Dewan M, Kim Y, Roosta T, Chadha A, Shah C. ClaimVer: Explainable Claim-Level Verification and Evidence Attribution of Text Through Knowledge Graphs. Findings of EMNLP. 2024:13613–13627. https://doi.org/10.18653/v1/2024.findings-emnlp.795

74. Robinson I, Webber J, Eifrem E. Graph Databases. 2nd ed. Sebastopol, CA: O’Reilly Media; 2015. ISBN 978-1-491-93200-1.

75. SQLite developers. EXPLAIN QUERY PLAN. https://sqlite.org/eqp.html (accessed 11 October 2026).

76. Neo4j. Understanding Query Plans. Cypher Manual. https://neo4j.com/docs/cypher-manual/current/planning-and-tuning/execution-plans/ (accessed 11 October 2026).

77. European Medicines Agency. Kerendia: English EPAR product information. Retrieved 10 October 2026. https://www.ema.europa.eu/en/documents/product-information/kerendia-epar-product-information_en.pdf

78. European Medicines Agency. Libmeldy: English EPAR product information. Retrieved 10 October 2026. https://www.ema.europa.eu/en/documents/product-information/libmeldy-epar-product-information_en.pdf

79. European Medicines Agency. Lenalidomide Mylan: English EPAR product information. Retrieved 10 October 2026. https://www.ema.europa.eu/en/documents/product-information/lenalidomide-mylan-epar-product-information_en.pdf

80. European Medicines Agency. Piqray: English EPAR product information. Retrieved 10 October 2026. https://www.ema.europa.eu/en/documents/product-information/piqray-epar-product-information_en.pdf

81. European Medicines Agency. Lumeblue (previously Methylthioninium chloride Cosmo): English EPAR product information. Retrieved 10 October 2026. https://www.ema.europa.eu/en/documents/product-information/lumeblue-epar-product-information_en.pdf

82. WHO Collaborating Centre for Drug Statistics Methodology. ATC/DDD Index: L04AX04 lenalidomide. Retrieved 10 October 2026. https://atcddd.fhi.no/atc_ddd_index/?code=L04AX04

83. WHO Collaborating Centre for Drug Statistics Methodology. ATC/DDD Index: L04AX07 dimethyl fumarate. Retrieved 10 October 2026. https://atcddd.fhi.no/atc_ddd_index/?code=L04AX07

84. European Medicines Agency. RoActemra: EPAR Product Information. https://www.ema.europa.eu/en/documents/product-information/roactemra-epar-product-information_en.pdf (retrieved 10 and 26 October 2026; snapshot identities in the experiment manifest and Supplement S7).

85. European Medicines Agency. Tuyory: EPAR Product Information. https://www.ema.europa.eu/en/documents/product-information/tuyory-epar-product-information_en.pdf (accessed 10 October 2026; document identity in the experiment manifest).

86. European Medicines Agency. Tocilizumab STADA (previously Tofidence): EPAR Product Information. https://www.ema.europa.eu/en/documents/product-information/tocilizumab-stada-epar-product-information_en.pdf (accessed 10 October 2026; document identity in the experiment manifest).

87. European Medicines Agency. Avtozma: EPAR Product Information. https://www.ema.europa.eu/en/documents/product-information/avtozma-epar-product-information_en.pdf (accessed 10 October 2026; document identity in the experiment manifest).

88. European Medicines Agency. Tyenne: EPAR Product Information. https://www.ema.europa.eu/en/documents/product-information/tyenne-epar-product-information_en.pdf (accessed 10 October 2026; document identity in the experiment manifest).

89. European Medicines Agency. Vfend: English EPAR product information. Retrieved 10 October 2026. https://www.ema.europa.eu/en/documents/product-information/vfend-epar-product-information_en.pdf

90. Swissmedic. Lists and directories: extended list of authorised human medicines and approved packs. Data dated 30 September 2026; retrieved 26 October 2026. https://www.swissmedic.ch/swissmedic/en/home/services/listen_neu.html

91. European Medicines Agency. Luxturna: English EPAR product information, sections 1, 2 and 4.2. Retrieved 26 October 2026. https://www.ema.europa.eu/en/documents/product-information/luxturna-epar-product-information_en.pdf
