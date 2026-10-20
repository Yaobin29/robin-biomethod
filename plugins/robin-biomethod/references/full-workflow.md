# Full workflow v0.2

The default material-design entry is `design --goal goal.json`, not manual drafting.
`setup`/`doctor` are prerequisite checks; a successful response from either is not design completion.

## Goal and unknowns

Use the task-format.md goal schema. Material, target definition/assay and scale basis must
be explicit. Ask the user about consequential ambiguity. A tolerance not yet decided may
be null when unknown_fields includes target.tolerance. Other unresolved facts go in
unknown_fields and assumption_notes; they force draft_missing_evidence, not invented facts.
A scale chosen solely for execution acceptance must be clearly marked as such.

## Commands

    python3 scripts/biomethod.py configure
    python3 scripts/biomethod.py configure --session-limit 12 --minutes 30
    python3 scripts/biomethod.py design --goal goal.json --query 'material synthesis'
    python3 scripts/biomethod.py design --goal goal.json --bundle evidence --run-dir new-job
    python3 scripts/biomethod.py design --goal goal.json --dry-run
    python3 scripts/biomethod.py status /path/to/job
    python3 scripts/biomethod.py evidence /path/to/job/harness

`configure` is model-free. No parameters displays/persists the current defaults. Positive
finite user limits replace the old artificial24/60caps. k is1..3. k1 needs8core sessions;
auto source screening plus method extraction add2, so the ordinary fresh workflow needs
at least10before repairs. A provided registered bundle skips screening, so the minimum is9.
k>1 needs7k+1reflection+1selector plus preparation. The program checks feasibility before
starting. Sixteen and45are upper limits, never targets or fixed credit prices.

All sessions share ONE persisted budget.json and deadline, including screening, method
extraction, original-core calls and bounded format repair. Failed calls count. Usage is
recorded when exposed; unavailable monetary amounts and actual model identity stay unknown.
Workers disable unrelated apps/plugins/memory/delegation and use frozen task sources.
The controller's public-literature access occurs before the frozen model comparison.

## Phase contract

workflow.json records intake, discovery, screening, full_text, method_extraction, freeze,
harness2 and delivery. Each starts as pending, then running/completed or failed. Explicit
external evidence is labeled completed_external_input, never misrepresented as native search.

The source screen cannot invent PMC ids; extraction cannot invent locators, quotes or
reported route values. Incomplete full-text acquisition is surfaced. Missing supplements
remain gaps and can prevent a lab-ready procedure. No suitable source => incomplete workflow,
not a generic method answer. The final candidate can legitimately remain a scientific draft
while the computational workflow is fully executed and its uncertainty is explicit.

The original Harness2 mechanism performs baseline, INV and DOM rule proposals and executions,
AGG composition and execution, final delivery selection and reflection. All core rollouts
must have receipt hashes and matching real Codex JSONL traces; editor calls must be present.
At k1 there is one final, so delivery selection is trivial and no selector inference is claimed.
KEEP_BASE/NO_ENTRY are valid outcomes, not a reason to manufacture a difference.

execution-evidence.json verifies process traces, original ledger, artifacts and final
controller-side document checks. stage-comparison.json lists actual stage outputs and their
parameter differences. execution-report.md links baseline/INV/DOM/AGG method reports.
Only verified=true plus workflow_complete=true supports a full-process completion claim.
An explicit dry run, curated demo, host draft, missing trace or tampered file cannot pass.

## Failures and recovery

A native DNS/network failure remains visible. If an authorized host search tool works,
record that provider/query and register acquired text, then use design --bundle. Preserve
the failed job and count its model attempts when setting remaining budget. Never silently
restart or extend a budget. General partly executed trees require a new bounded run.
The guarded k1 final-only continuation below is the sole checkpoint exception.

Budget/time/account errors stop new calls; source and intermediate records remain private.
Actual scientific improvement requires independent tasks and experiments. Neither a full
pipeline nor a perfect document score licenses chemical, safety or reproducibility claims.

A failed core can reuse already validated frozen preparation with a NEW upstream tree:

    python3 scripts/biomethod.py design --goal goal.json --prepared-from failed-job \
      --session-limit REMAINING --minutes REMAINING --run-dir new-private-job

Goal equality and frozen-source hashes are checked. Session/time limits must fit the
previous job's remaining allowance; the new record identifies reused preparation.
The failed core tree remains untouched. Individual calls allow up to600seconds, still
bounded by the shared deadline; partial traces are preserved on timeout.

## Separate delivery contract repair

If all original stages ran but the selected JSON fails the public contract, up to one
format repair plus one retry may use the SAME remaining budget. Original baseline/INV/DOM/AGG
files are retained. Only numeric expressions and proposed validation-experiment coverage may
change; frozen scientific parameter values, evidence, constraints and uncertainty stay fixed.
The separate delivery-repair receipt binds the original and repaired files to actual transport.
The report shows both original selected assessment and delivery assessment. It does not claim
the original AGG passed when only the separate repair passed. For an already completed core:

    python3 scripts/biomethod.py repair-delivery /path/to/job

This does not restart a deadline or grant new sessions. Without a complete original core,
it cannot substitute for missing stages.

## Failed final-only continuation

`resume-final JOB --minutes REMAINING` supports only a parallel k1 run with three intact
successful baseline/INV/DOM artifacts, three actual rule proposals, and a missing AGG output.
It verifies saved source/output receipts and equality with the original harvested AGG tree.
Only final execution, native trivial selection and native reflection are called; the pinned
upstream algorithm is unchanged. The previous report, workflow, budget and native summary
are retained in final-recovery-history. Pauses do not consume active execution allowance;
prior active time and all failed sessions still count. Existing final artifacts cannot be
silently overwritten. Other partial trees require a fresh, explicitly bounded run.
