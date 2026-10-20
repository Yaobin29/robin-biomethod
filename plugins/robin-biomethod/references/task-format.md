# RobinBioMethod task format v1

Use scripts/biomethod.py from the plugin root. No global skills are required.

## Goal

A goal.json object contains schema_version=1, material, application, target, scale,
constraints, available_equipment and optional unknowns. Target needs metric, numeric
value and nonnegative tolerance, unit, definition and assay. Scale needs positive
value, unit and basis (e.g. precursor mass, not final product yield). Each constraint
has a unique id, kind hard/preference and description. Unknown target definitions or
assays must be clarified, not filled with a model's preferred interpretation.
See examples/gelma/goal.json for an explicitly hypothetical example.

## Registered evidence

A collection has registry.json and documents/*.txt. Each document includes id, title,
doi when available, stable url, access, license, text_file and SHA256. Allowed access:
full_text, user_supplied_full_text, curated_excerpt. Each text line has a unique
[L0001]-style locator. Quotes are checked against document id AND locator.

`collect` retrieves selected Europe PMC fullTextXML; sections, tables and captions
are numbered. Supplement links are recorded, not silently treated as read. `import`
accepts PDF or extracted UTF-8 TXT/MD. `merge` combines collections with distinct ids.
Neither source availability nor exact quote matching proves chemical entailment.

Method cards are a JSON array. Each has id (route identity), document (one source id),
name, parameters and limitations. A parameter has name, value, unit and evidence
[{document,locator,quote}]. Unknown values are null with missing_reason. A different
paper's condition cannot be labeled as this route's reported condition. Method cards
are human/host extracted inputs and require source review; no automatic extraction
model is hidden inside preparation.

## Preparation and output

    python3 scripts/biomethod.py prepare --goal goal.json --bundle evidence \
      --methods method-cards.json --out new-task [--profile material-profile.json]

Preparation freezes inputs into source/ and creates base/, prompt.txt and task.json.
The source registry must contain any cited supplement as a distinct registered source.
A material profile contains id and checks; no material is assumed when omitted.
Libraries are conservatively scoped by material; no automatic cross-material transfer.

Output/method.json follows the complete contract in assets/task-prompt.txt. It includes
candidate_methods, target_assessment, constraint_assessments, uncertainties and
validation_experiments. Parameter origins: reported, calculated, proposed, unknown.
Reported values and units match route cards; calculated fields expose arithmetic and
assumptions; proposals link rationale and uncertainty; unknowns remain null.
The only method statuses are candidate_unvalidated and draft_missing_evidence.

    python3 scripts/biomethod.py assess --task new-task/task.json --artifact method.json
    python3 scripts/biomethod.py render --task new-task/task.json --artifact method.json --out method.md
    python3 scripts/biomethod.py compare --task new-task/task.json \
      --artifact baseline.json --artifact candidate.json --out comparison.json

Assessment checks structure, quote provenance, declared arithmetic and coverage. It
cannot verify the truth of every interpretation, dimensional assumption, biological
claim or proposed acceptance threshold. A perfect document score is not scientific
success. Critical conditions or hard constraints unresolved => draft_missing_evidence.

A model trial is a separate explicit action:

    python3 scripts/biomethod.py run --task new-task/task.json \
      --holdout other-task/task.json --session-limit 16 --minutes 45

Prepare holdouts before the run. Changing only a task id, duplicating the same problem
or lightly rephrasing a source is not scientific independence. Never use holdouts as
editing context or let a candidate rewrite the evaluator. User confirms model budget.
The inherited engine has hard caps24sessions/60minutes. Defaults here are16/45.
No adopt command is exposed: documentation improvement cannot authorize scientific use.
