# Scientific Lint for experimental plans and candidate SOPs (v1)

Scientific Lint is a **separate design review** after evidence-bound method generation,
not a replacement for `assess`, not part of the pinned Harness2 evaluator and never a
laboratory safety approval. It does not change the frozen goal, literature, method cards,
selected method or original INV/DOM/AGG execution results.

## Two gates

1. **Intake (no model needed)**: `GOAL-001` unknown target tolerance,
   `GOAL-002` unspecified available equipment, `GOAL-003` no explicit constraints.
   These are warnings because a partial brief can legitimately be explored as a draft.
2. **Candidate design / SOP**: reuse the existing trusted `assess` for structural,
   provenance and arithmetic errors (`DOC-*`). Additionally detect non-finite numbers
   (`SOP-001`, error), numeric values with missing units (`SOP-002`, warning),
   duplicate within-step parameter names (`SOP-003`, warning), unresolved hard constraints
   (`PLAN-001`, warning), one-batch pilot limits (`PLAN-002`, warning), and potential
   readout/target terminology mismatch (`PLAN-003`, warning).

`candidate_for_human_review` means machine checks found no blocking error and no
encoded unresolved prerequisites. It **never** means lab-ready. `unresolved_draft`
means a draft has unknown method parameters, missing target tolerance or unresolved
hard constraints; the agent must preserve those uncertainties. `machine_check_failed`
means the document or numeric checks failed and needs correction.

## Human-only questions

A reviewer must explicitly judge precursor identity, chemistry, route transfer,
parameter interactions, scale, purification endpoints, experiment controls,
measurement specificity/calibration, statistical design, and safety approvals.
Material-specific `profile.checks` are *review prompts* derived from task evidence,
not executable hard rules and not trusted source instructions.

## How to extend safely

When a repeated error appears, add a minimally scoped rule with: stable ID,
triggered input path, objective pass/fail condition, severity, a counterexample,
expected repair and a unit test. Keep ambiguous chemistry claims as human review
questions. New numerical thresholds need a documented source, target and context;
never convert a material-specific value into a universal check. Review the rule
against at least one valid and one invalid case before enabling it as an error.

## Commands and artifacts

```sh
python3 scripts/biomethod.py lint-sop --task JOB/task/task.json --artifact METHOD.json --out JOB/lint-manual.json
```

The default `design` workflow records `intake-lint.json` and writes
`scientific-lint.json` for evidence-verified final delivery. Its scientific lint
status must be shown alongside, not confused with, the Harness2 process-completion
status. It does not authorize wet-lab execution or automatic release of an SOP.
