"""Deterministic scientific design/SOP lint; not laboratory authorization.

This gate is intentionally separate from the frozen Harness2 evaluator.
Hard document errors remain the responsibility of validation.assess.
Scientific interpretation is always left for qualified human review.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from robinharness.runtime import dump
from .validation import assess
from .workflow import read

RULESET_VERSION = "scientific-lint/1.0"
_DIMENSIONLESS = frozenset({
    "ph", "ratio", "molar ratio", "mass ratio", "count", "number",
    "cycles", "cycle count", "replicate count", "replicates",
})
_UNKNOWN_UNITS = frozenset({"", "?", "na", "n/a", "none", "unknown", "tbd"})


def _finding(code, severity, path, message, next_action):
    return dict(id=code, severity=severity, path=path, message=message,
                next_action=next_action)


def lint_goal(goal):
    """Nonblocking intake prompts for a previously schema-validated goal.

    This is a completeness prompt, not a substitute for workflow.validate_goal.
    """
    findings = []
    target = goal.get("target", {}) if isinstance(goal, dict) else {}
    if isinstance(target, dict) and target.get("tolerance") is None:
        findings.append(_finding("GOAL-001", "warning", "target.tolerance",
            "Target tolerance is not decided; preserve it as an unknown.",
            "Specify a justified tolerance or keep draft_missing_evidence."))
    if not goal.get("available_equipment"):
        findings.append(_finding("GOAL-002", "warning", "available_equipment",
            "Available equipment has not been established.",
            "Confirm instruments, calibration/qualification and processing capabilities."))
    if not goal.get("constraints"):
        findings.append(_finding("GOAL-003", "warning", "constraints",
            "No explicit constraints are recorded.",
            "Confirm material supply, equipment, safety and process constraints; an empty list can be intentional."))
    return dict(ruleset=RULESET_VERSION, stage="intake", warnings=findings,
                status="review_inputs" if findings else "intake_documented",
                laboratory_authorized=False)


def lint_candidate(source, artifact):
    """Inspect candidate design without making chemistry, efficacy or safety claims.

    Hard failures are structural/provenance issues. Scientific issues are
    documented as warnings or human-review questions, not invented verdicts.
    """
    source, artifact = Path(source), Path(artifact)
    base = assess(source, artifact)
    findings = []
    if not base.get("valid"):
        for i, error in enumerate(base.get("errors", []) or ["Existing document assessment failed."], 1):
            findings.append(_finding(f"DOC-{i:03d}", "error", "method.json",
                str(error), "Correct the documented contract/provenance error and rerun assess."))
    try:
        data, goal = read(artifact), read(source / "goal.json")
        profile = read(source / "profile.json") if (source / "profile.json").is_file() else {}
        if not isinstance(data, dict) or not isinstance(goal, dict):
            raise ValueError("method artifact and goal must be JSON objects")
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        findings.append(_finding("DOC-READ", "error", "source/method.json",
            f"Unable to inspect JSON: {exc}", "Repair source/artifact access and rerun the gate."))
        data, goal, profile = {}, {}, {}

    target = goal.get("target", {}) if isinstance(goal.get("target", {}), dict) else {}
    unresolved = bool(goal.get("unknown_fields") or data.get("status") == "draft_missing_evidence")
    if target.get("tolerance") is None:
        unresolved = True
    methods = data.get("candidate_methods") if isinstance(data.get("candidate_methods"), list) else []
    for mi, method in enumerate(methods):
        if not isinstance(method, dict):
            continue
        steps = method.get("steps") if isinstance(method.get("steps"), list) else []
        for si, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            names = set()
            params = step.get("parameters") if isinstance(step.get("parameters"), list) else []
            for pi, param in enumerate(params):
                if not isinstance(param, dict):
                    continue
                path = f"candidate_methods[{mi}].steps[{si}].parameters[{pi}]"
                name = str(param.get("name", "")).strip()
                key = name.casefold()
                if key in names and key:
                    findings.append(_finding("SOP-003", "warning", path + ".name",
                        f"Repeated parameter name within a step: {name}.",
                        "Confirm duplicates are intentional or give each parameter an unambiguous name."))
                names.add(key)
                value = param.get("value")
                if isinstance(value, (float, int)) and not isinstance(value, bool):
                    if not math.isfinite(value):
                        findings.append(_finding("SOP-001", "error", path + ".value",
                            "Numeric value is NaN or infinite.",
                            "Supply a finite, source-grounded value or mark the parameter unknown."))
                    unit = str(param.get("unit") or "").strip().casefold()
                    if unit in _UNKNOWN_UNITS and key not in _DIMENSIONLESS:
                        findings.append(_finding("SOP-002", "warning", path + ".unit",
                            "A numeric SOP parameter has no explicit unit or dimensionless rationale.",
                            "Record a unit with basis, or document why this parameter is dimensionless."))
                if param.get("origin") == "unknown":
                    unresolved = True
            if not step.get("action"):
                # Covered by assess, retained here only as a human-readable location.
                continue
    constraints = goal.get("constraints") if isinstance(goal.get("constraints"), list) else []
    hard = {c.get("id"): c.get("kind") == "hard" for c in constraints if isinstance(c, dict)}
    assessments = data.get("constraint_assessments") if isinstance(data.get("constraint_assessments"), list) else []
    for ci, assessment in enumerate(assessments):
        if isinstance(assessment, dict) and hard.get(assessment.get("id")) and assessment.get("status") != "compatible":
            unresolved = True
            findings.append(_finding("PLAN-001", "warning", f"constraint_assessments[{ci}]",
                "An unresolved/violated hard constraint prevents SOP release.",
                "Resolve the hard constraint with traceable evidence; do not imply laboratory approval."))
    experiments = data.get("validation_experiments") if isinstance(data.get("validation_experiments"), list) else []
    for ei, experiment in enumerate(experiments):
        if not isinstance(experiment, dict):
            continue
        if experiment.get("independent_batches") == 1:
            findings.append(_finding("PLAN-002", "warning", f"validation_experiments[{ei}].independent_batches",
                "One independent synthesis batch cannot estimate batch-to-batch variation.",
                "Explain the pilot scope or propose independent batches appropriate to the goal."))
    readouts = [r for e in experiments if isinstance(e, dict)
                for r in (e.get("readouts") if isinstance(e.get("readouts"), list) else []) if isinstance(r, dict)]
    target_metric = str(target.get("metric") or "").strip().casefold()
    if readouts and target_metric and not any(target_metric in str(r.get("metric", "")).casefold() for r in readouts):
        findings.append(_finding("PLAN-003", "warning", "validation_experiments[*].readouts",
            "No readout metric exactly names the declared target; synonyms may still be valid.",
            "Human reviewer must verify readout-to-target construct validity and normalization."))
    prompts = [
        "Does precursor identity (source, grade, molecular weight/lot) support this exact route?",
        "Are reaction chemistry, parameter interactions, scaling and purification endpoints justified for this material?",
        "Do the chosen controls isolate the central causal hypothesis and potential confounders?",
        "Does the measurement assay actually quantify the target as defined, with calibration and normalization?",
        "Are biological/technical replicates, batch allocation and decision thresholds fit for the intended inference?",
        "Have hazards, equipment qualification, approvals and operator-specific requirements been reviewed outside this Agent?",
    ]
    if isinstance(profile, dict):
        prompts.extend(str(x) for x in profile.get("checks", []) if isinstance(x, str) and x.strip())
    has_error = any(f["severity"] == "error" for f in findings)
    review_status = "machine_check_failed" if has_error else ("unresolved_draft" if unresolved else "candidate_for_human_review")
    return dict(ruleset=RULESET_VERSION, stage="candidate_design_and_sop",
                source_artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact.is_file() else None,
                valid=not has_error, document_assessment_valid=bool(base.get("valid")),
                status=review_status, findings=findings, human_review_questions=prompts,
                unresolved_critical_prerequisites=unresolved,
                laboratory_authorized=False, experimental_validity="not established",
                notes="A passing lint verifies only encoded checks; human scientific and safety review plus laboratory validation remain necessary.")


def save_job_lint(job, proof):
    """Save after evidence-verified delivery selection; never edit the selected artifact."""
    job = Path(job)
    artifact = proof.get("delivery_artifact")
    if not proof.get("verified") or not artifact:
        raise ValueError("Scientific lint requires verified delivery artifact provenance.")
    result = lint_candidate(job / "task/source", Path(artifact))
    dump(job / "scientific-lint.json", result)
    return result
