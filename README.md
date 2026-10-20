![RobinBioMethod — From Literature to Protocol](assets/robin-biomethod-banner.png)

# RobinBioMethod

*Conceptual workflow: the software produces candidate methods and validation plans; synthesis and experimental validation are performed in the laboratory.*
[中文说明](README.zh-CN.md)

An independent Codex plugin for evidence-grounded **biomaterial synthesis methods plus
minimal validation experiments**, built on pinned Google Research Harness² and Robinharness.
Material-neutral workflow; GelMA is a public example, not a default recipe.

## Install locally or from a downloaded checkout

Requirements: macOS/Linux, Python3.12/3.13. Windows uses WSL. Real trials additionally need
Codex CLI>=0.147.0, file-backed Codex login and available account allowance. Offline demo
and document checks need no login, model call or network. Standard-library core, no pip install.

From this complete repository (retain hidden .agents folder):

    codex plugin marketplace add .
    codex plugin add robin-biomethod@robin-biomethod

Or install directly from GitHub:

    codex plugin marketplace add Yaobin29/robin-biomethod --ref main
    codex plugin add robin-biomethod@robin-biomethod

Repository: https://github.com/Yaobin29/robin-biomethod

Open a new chat; invoke $biomethod-setup or $biomethod-design. In the skill picker, these
may appear as robin-biomethod:biomethod-setup / robin-biomethod:biomethod-design.
The narrowly triggered skills do not start optimization for ordinary research.

All commands below use the entry point from the repository root:

    python3.12 plugins/robin-biomethod/scripts/biomethod.py --help

Use your Python3.12/3.13 executable. There is no required global Robin skill installation.

## Research to method

1. Define the material, application, target metric/definition/assay/tolerance, precursor
   scale, equipment and hard constraints. Never silently maximize functionalization.
2. Search public metadata, select papers, acquire actual Methods and supplements, then
   extract cited route-specific method cards. Discovery summaries alone are insufficient.
3. Freeze goal, registered evidence, method cards and a material-specific profile if needed.
4. Draft in the host conversation, assess and render; or explicitly request a bounded
   real Harness² trial. These are different operations and must be labeled correctly.
5. Deliver candidates, conflicts, unknowns and minimal experiments. Human review and
   laboratory evidence are required before calling a synthesis successful.

For brevity, set BM to the entry point when following these examples in your shell:

    BM=plugins/robin-biomethod/scripts/biomethod.py
    python3.12 "$BM" search --query 'biomaterial synthesis target property' --out search.json
    python3.12 "$BM" collect --pmcid PMC4977492 PMC6499775 --search search.json --out evidence
    python3.12 "$BM" import --input supplement.txt --id supplement1 --title 'Supplement' \
      --url 'https://publisher.example/supplement' --out supplement-evidence
    python3.12 "$BM" merge --bundle evidence --bundle supplement-evidence --out combined
    python3.12 "$BM" prepare --goal goal.json --bundle combined --methods method-cards.json --out task
    python3.12 "$BM" assess --task task/task.json --artifact method.json
    python3.12 "$BM" render --task task/task.json --artifact method.json --out method.md

Choose real query/identifiers for your own material; the PMC ids above illustrate GelMA.
`search --provider pubmed` uses the PubMed-indexed subset of Europe PMC (SRC:MED), not
Google Scholar. Search records metadata; 3W fields and method cards require host/human
full-text review. collect lists supplements without claiming to have read them.
PDF import uses optional pdftotext. OpenDataLoader/Zotero are optional host-side inputs;
this release does not bundle their services. Text/Markdown import always remains available.

Full interfaces: plugins/robin-biomethod/references/task-format.md.

## INV, DOM and composition

INV changes HOW the agent works: acquisition coverage, source tracking, calculation,
constraint enumeration, uncertainty handling and completion checks.
DOM changes the task-scoped practitioner model: material identity, mechanism, coupled
conditions, scope of transfer, characterization and discriminating experiment design.
Numerical material facts remain task evidence; they are not universal DOM rules.

Harness² edits these RULES and re-executes the drafting task. Its aggregator may merge
justified rule edits, choose one or KEEP_BASE. It must not concatenate incompatible
recipes. Workers see only frozen evidence and cannot search the network during comparison.

An explicitly authorized model trial:

    python3.12 "$BM" run --task task/task.json --holdout independent-task/task.json \
      --session-limit 16 --minutes 45

Defaults: k1, parallel, 16sessions/45minutes; inherited hard caps24/60. Retries count.
At k1 there is one final and no comparative selector call. Model selection uses the CLI's
own default; --model requests a specific model, with no silent fallback. Costs stay
unknown when not supplied. A prepared task or setup is not permission for an extra trial.
Stage outputs and assessments are exported alongside candidate-method.md and report.json.
No adopt command: documentation-score improvement cannot authorize scientific adoption.

## Offline public example

    python3.12 "$BM" demo --out /path/to/new-example-folder

This copies and renders a **host-curated** two-paper GelMA example. It makes zero model
calls and does not pretend INV/DOM discovered an improvement. The hypothetical target is
70±5% primary-amine conversion at5g precursor scale, not the article authors' guaranteed
outcome. Type-A and type-B source routes differ; the TFF route is reference-only because
that equipment is unavailable in the example. Missing purification and target-calibration
evidence remain explicit. The delivery is a draft with minimal experiments, not a lab SOP.
CC BY4.0 article excerpt attribution is in plugin NOTICE and source registries.

## Checks and limits

    python3.12 -m unittest discover -s plugins/robin-biomethod/tests -q

Controller checks detect missing fields, invalid quotes, changed reported values/units,
route-document mixing, declared arithmetic mismatch, unresolved constraints and unlinked
critical uncertainties. They do not prove chemical entailment, dimensional assumptions,
assay validity, safety, purity, biocompatibility or target achievement. Review these manually.
Minimum experiments include controls, independent synthesis batches, nested technical
repeats, qualified readouts, predictions, falsification and result-dependent actions.
Sample counts are justified pilot proposals unless a valid power analysis is supplied.

Private state: ~/.local/share/robin-biomethod, overridden by ROBINBIOMETHOD_HOME.
Source papers and run logs remain outside installation/release packages by default.
Remove via codex plugin remove robin-biomethod@robin-biomethod; data remains local.
See VALIDATION.md for actually verified boundaries. Installation does not create GitHub
repositories or publish user experiments. No Notion write, wet-lab action or GelMA dialysis model is bundled.
