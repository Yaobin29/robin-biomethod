---
name: method-design
description: Load for source-grounded biomaterial synthesis method drafting with a frozen goal and evidence package.
---
Read source/goal.json, registry.json, method_cards.json and profile.json. Inspect original
numbered document lines, not just method cards. Follow the material-scoped profile; do
not assume the material is GelMA. Prioritize explicit hard constraints and target assay.

Keep reported values separate from calculations and proposals. Reported parameters must
match their route card and have exact document/locator/quote evidence. Calculations expose
arithmetic and scaling/unit assumptions; matching arithmetic is not proof of scale transfer.
If a condition is missing, use origin unknown, value null and an uncertainty link. Do not
patch it with a condition from another route. A proposal needs a rationale and uncertainty
link. A new target value is a requirement, not an observed result. Do not interpolate a
feed ratio to guarantee a target property without supporting evidence.

Produce method.json using the task prompt's contract. Include steps, inputs, checkpoints,
characterization, gaps, constraint assessments and linked validation experiments. Preserve
independent synthesis batches separately from technical repeats. Each experiment states
hypothesis, readouts, controls, prediction, falsification and the next action for each result.
Use draft_missing_evidence when key conditions or hard constraints remain unresolved.
Keep competing routes when evidence cannot choose; never force agreement or a merged recipe.
Reopen the JSON and check ids, units, evidence references and uncertainty coverage before finishing.

Run `python3 scripts/check_method.py output/method.json` and fix its errors before delivery. Keep reported parameter names/values/units identical to the frozen route card. Unknown fields in goal.json force draft_missing_evidence and need explicit uncertainty coverage.
