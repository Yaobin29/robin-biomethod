# Article-style bilingual scientific reports

Primary delivery is report.html. Structure: Aim and boundaries → literature understanding
→ candidate synthesis method → unresolved questions → minimal validation → references and
evidence assessment. Baseline/INV/DOM/AGG belongs inside a closed candidate-development
support panel, rather than a separate main chapter before the reader sees the method.
Use one material-specific heading, without a second marketing-style subtitle.

## Language is content, not just interface labels

The host prepares a source-bound translation pack after the final method is frozen:

    python3 scripts/biomethod.py report-texts JOB --out JOB/report-localization.json

Complete every zh value. Source prose already in Chinese also requires an en translation.
Never overwrite source JSON to translate it. The template binds goal, final method and
literature extract through source_hash. Re-export if any of those changes. Preserve all
numerical values, unknowns, conditions, claims and falsification/decision branches. Original
paper titles, original quotations, identifiers, units and formulas may retain their language.
Translate scientific prose throughout the selected edition, not just column headings.

Optional presentation fields in the same pack:

- method_flow: map method ID to one item per actual step, with zh/en label and purpose.
  These are faithful captions, not additional chemistry. Numeric conditions are rendered
  directly from original parameters; unknown counts stay visible. Do not invent a route.
- material_overview: zh/en short material explanation bounded by the registered sources.
  One paper is not an exhaustive account of the field.
- experiment_roadmap: items with id and zh/en label/resolves; derive the prerequisites and
  what can be resolved from the actual experiment design. Keep blocked experiments blocked.
- rule_summaries: label -> zh/en concise summaries. They require rule_hash equal to SHA-256
  of sorted, ensure_ascii=False JSON of the actual rule_edits list. Original full stage
  methods and machine records stay in the English archival view, explicitly labeled.
- reference_assessments: document ID -> list of zh/en dimension/finding objects. State
  directness, reporting completeness, within-study replication and task applicability only
  to the extent the registered evidence supports them. Never invent independent replication.

    python3 scripts/biomethod.py html-report JOB --localization JOB/report-localization.json

The saved report automatically reuses JOB/report-localization.json. Missing translations
produce an honestly labeled source-language edition with the unavailable language disabled;
this is not completed bilingual delivery. Missing/stale translations or altered numeric
tokens in an explicitly supplied pack fail closed. Translation is performed by the host,
not silently outsourced to a worker or added as an unbudgeted model session. Numeric-token
checks are necessary but not semantic proof: review the translated scientific meaning.

The machine-readable report-presentation.json records language readiness separately from
execution proof. A completed scientific computation does not imply completed localization.
When both languages are requested, deliver only after localization_complete=true.

## Reading hierarchy

Aim states the task, assay definition, scale and boundaries. Methods show a labeled
synthesis flowchart with actual-step links, key source parameters and visible unknowns,
then detailed parameter/value/origin tables. Quotes and calculations fold at the parameter.
Unresolved questions precede experiments. The experiment table answers what to test, what
to measure, and what can be determined, with planned batches distinct from technical repeats.
Controls, sample handling, acceptance and pass/fail/inconclusive decisions start folded.

Support panels start closed. Preserve originals and the prior HTML snapshot when revising a
user report. Editorial composition adapts frontend-design and restrained frontend-skill
principles; no additional skill is needed at runtime. Report languages switch with native
radio controls and CSS: no JavaScript, CDN, font download or network resource is required.
Each language panel has its own lang attribute and unique anchors. Source text is escaped.

## Reference metadata and confidence

Metadata retrieval is an explicit, optional operation, not a hidden network request:

    python3 scripts/biomethod.py html-report JOB --refresh-references

Caches journal/year/citation count, provider, exact DOI/PMCID lookup and timestamp in
reference-profile.json. Retrieval failure remains unknown, never zero. Normal rendering
reuses the dated cache and stays offline. Citation count measures influence, not independent
reproductions. Journal metrics cannot certify the scientific content of an individual paper.
Show evidence dimensions and task-specific support; do not assign a probability from journal
name or citation count. Independent replication stays unassessed until actual methods and
results of other groups are reviewed. See https://sfdora.org/read/ for assessment principles.

## Presentation validation

Tests cover both language panels, full translation coverage, stale/numeric/passthrough guards,
English prose without Chinese UI, closed disclosures, semantic flowcharts, article order,
quoted source/readout preservation, unique stage/final anchors and unsafe-content escaping.
Metadata tests cover exact identity, dated counts, unavailable lookups and invalid numbers.
Synthetic test translations test routing only; they are not scientific translation evidence.
The live HAMA artifact has a separately reviewed local translation pack and metadata cache.
No wet-lab validity or browser visual/print certification follows from these checks.
