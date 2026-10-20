"""Trusted structural/provenance checks, explicitly NOT a chemistry validation oracle."""
from __future__ import annotations
import ast
from decimal import Decimal
import json
from pathlib import Path
from .workflow import read, validate_task_source, source_index, check_cites


def calculate(expression):
    """Evaluate arithmetic only; no names, calls, attributes or arbitrary Python."""
    if not isinstance(expression, str) or len(expression) > 160:
        raise ValueError("Provide a short arithmetic expression.")
    def visit(n):
        if isinstance(n, ast.Expression):
            return visit(n.body)
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return Decimal(str(n.value))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            return visit(n.operand) * (-1 if isinstance(n.op, ast.USub) else 1)
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = visit(n.left), visit(n.right)
            if isinstance(n.op, ast.Add):return a + b
            if isinstance(n.op, ast.Sub):return a - b
            if isinstance(n.op, ast.Mult):return a * b
            return a / b
        raise ValueError("Only arithmetic + - * / is permitted.")
    return visit(ast.parse(expression, mode="eval"))


def inspect_artifact(source, data):
    goal, docs, cards, profile = validate_task_source(source)
    _, lines = source_index(source)
    errors, warnings = [], []
    passed = 0
    def require(test, message):
        nonlocal passed
        if test:passed += 1
        else:errors.append(message)
    def strings(value):
        return isinstance(value, list) and bool(value) and all(isinstance(x, str) and x.strip() for x in value)
    require(data.get("schema_version") == 1, "artifact schema_version must be 1")
    require(data.get("material") == goal["material"], "artifact material does not match frozen goal")
    require(data.get("status") in ("candidate_unvalidated", "draft_missing_evidence"), "method must remain explicitly unvalidated")
    if goal.get("unknown_fields"):
        require(data.get("status") == "draft_missing_evidence", "unresolved goal fields require draft_missing_evidence")
    require(data.get("target_assessment", {}).get("status") in ("unvalidated", "unsupported"), "target achievement cannot be asserted without experimental results")
    require(isinstance(data.get("target_assessment", {}).get("reason"), str) and bool(data["target_assessment"]["reason"].strip()), "target assessment requires a bounded reason")
    require(bool(data.get("evidence_limitations")) and strings(data.get("evidence_limitations")), "state evidence limitations")
    uncertainties = data.get("uncertainties", [])
    require(isinstance(uncertainties, list) and bool(uncertainties), "declare remaining uncertainties")
    uids, critical = set(), set()
    if isinstance(uncertainties, list):
        for u in uncertainties:
            if not isinstance(u, dict):errors.append("invalid uncertainty");continue
            uid = u.get("id")
            require(isinstance(uid, str) and bool(uid) and uid not in uids and bool(u.get("question")), "uncertainty needs unique id and question")
            require(u.get("importance") in ("critical", "minor"), "uncertainty importance must be critical or minor")
            uids.add(uid)
            if u.get("importance") == "critical":critical.add(uid)
    routes = {c["id"]: c for c in cards}
    methods = data.get("candidate_methods", [])
    require(isinstance(methods, list) and bool(methods), "at least one candidate method required")
    mids, observed_unknown = set(), False
    if isinstance(methods, list):
        for method in methods:
            if not isinstance(method, dict):errors.append("invalid candidate method");continue
            mid = method.get("id");rid = method.get("route_id")
            require(isinstance(mid, str) and bool(mid) and mid not in mids, "candidate needs unique method id")
            mids.add(mid)
            require(rid in routes, "candidate must retain a registered route_id")
            require(strings(method.get("inputs")), "method needs inputs/reagents/equipment")
            require(strings(method.get("checkpoints")), "method needs process checkpoints")
            require(strings(method.get("characterization")), "method needs characterization/readouts")
            require(strings(method.get("gaps")), "method needs explicit transfer and missing-evidence gaps")
            steps = method.get("steps", [])
            require(isinstance(steps, list) and bool(steps), "method needs steps")
            if not isinstance(steps, list):continue
            for step in steps:
                if not isinstance(step, dict):errors.append("invalid method step");continue
                require(bool(step.get("action")), "step requires an action")
                params = step.get("parameters", [])
                require(isinstance(params, list) and bool(params), "step requires parameter records (unknown is allowed)")
                if not isinstance(params, list):continue
                for p in params:
                    if not isinstance(p, dict):errors.append("invalid parameter");continue
                    origin = p.get("origin")
                    require(bool(p.get("name")) and isinstance(p.get("unit"), str), "parameter needs name and unit")
                    require(origin in ("reported", "calculated", "proposed", "unknown"), "invalid parameter origin")
                    cites = p.get("evidence", [])
                    if origin in ("reported", "calculated"):
                        require(check_cites(cites, docs, lines), "reported/calculated parameter has missing or invalid evidence")
                        same_route = all(isinstance(c, dict) and c.get("document") == routes.get(rid, {}).get("document") for c in cites) if isinstance(cites, list) else False
                        require(same_route, "reported/calculated parameter splices another route's document")
                    if origin == "reported":
                        require(any(x.get("name") == p.get("name") and x.get("value") == p.get("value") and x.get("unit") == p.get("unit") for x in routes.get(rid, {}).get("parameters", [])), "reported parameter differs from the frozen method card")
                    if origin == "calculated":
                        try:
                            result = calculate(p.get("expression"))
                            value = Decimal(str(p.get("value")))
                            require(result.is_finite() and value.is_finite() and abs(result-value) <= max(Decimal('0.000001'), abs(result)*Decimal('0.000001')), "arithmetic result mismatch")
                        except (ValueError, TypeError, SyntaxError, ArithmeticError):errors.append("invalid arithmetic calculation")
                        require(bool(p.get("assumptions")), "calculation must expose scaling/unit assumptions")
                    if origin == "proposed":
                        require(bool(p.get("rationale")) and p.get("uncertainty_id") in uids, "proposal requires rationale and linked uncertainty")
                        if cites:require(check_cites(cites, docs, lines), "invalid proposal citation")
                    if origin == "unknown":
                        observed_unknown = True
                        require(p.get("value") is None and bool(p.get("reason")) and p.get("uncertainty_id") in uids, "unknown parameter needs null value, reason and uncertainty link")
                    elif origin in ("reported", "calculated", "proposed"):
                        require(p.get("value") is not None, "non-unknown parameter cannot have null value")
    if observed_unknown:
        require(data.get("status") == "draft_missing_evidence", "missing method conditions require draft_missing_evidence status")
    assessments = data.get("constraint_assessments", [])
    require(isinstance(assessments, list), "constraint assessments must be a list")
    expected_c = {c["id"] for c in goal["constraints"]}
    seen_c = []
    if isinstance(assessments, list):
        for c in assessments:
            if not isinstance(c, dict):errors.append("invalid constraint assessment");continue
            seen_c.append(c.get("id"))
            require(c.get("status") in ("compatible", "violated", "unknown") and bool(c.get("reason")), "constraint requires explicit status and reason")
            if c.get("status") in ("violated", "unknown"):
                require(data.get("status") == "draft_missing_evidence" or next((x["kind"] for x in goal["constraints"] if x["id"] == c.get("id")), None) != "hard", "unresolved hard constraint requires draft status")
        require(set(seen_c) == expected_c and len(seen_c) == len(expected_c), "constraint coverage is incomplete or duplicated")
    experiments = data.get("validation_experiments", [])
    require(isinstance(experiments, list) and bool(experiments), "minimal validation experiment required")
    covered = set()
    if isinstance(experiments, list):
        eids = set()
        for e in experiments:
            if not isinstance(e, dict):errors.append("invalid experiment");continue
            require(bool(e.get("id")) and e.get("id") not in eids, "experiment needs unique id");eids.add(e.get("id"))
            targets = e.get("uncertainty_ids", [])
            require(isinstance(targets, list) and bool(targets) and set(targets).issubset(uids), "experiment must address declared uncertainty")
            if isinstance(targets, list):covered.update(targets)
            for key in ("hypothesis", "predicted_result", "falsification", "decision_rule", "sampling", "sample_size_rationale"):
                require(isinstance(e.get(key), str) and bool(e[key].strip()), f"experiment requires {key}")
            require(strings(e.get("controls")), "experiment needs controls")
            require(strings(e.get("method_ids")) and set(e["method_ids"]).issubset(mids), "experiment must identify candidate method(s)")
            for key in ("independent_batches", "technical_repeats"):
                require(type(e.get(key)) is int and e[key] >= 1, f"experiment requires positive {key}")
            readouts = e.get("readouts", [])
            require(isinstance(readouts, list) and bool(readouts), "experiment needs measurable readouts")
            if isinstance(readouts, list):
                for r in readouts:
                    require(isinstance(r, dict) and all(isinstance(r.get(k), str) and bool(r[k].strip()) for k in ("metric", "method", "unit", "acceptance", "acceptance_basis")), "readout needs metric, assay, unit and acceptance with basis")
    require(critical.issubset(covered), "critical uncertainty has no discriminating experiment")
    warnings.extend(["Checks verify structure, declared arithmetic and provenance, not chemical entailment or experimental efficacy.", "Human review must verify source interpretation, route compatibility, hazard controls and assay suitability."])
    warnings.extend(str(x) for x in profile.get("checks", []))
    total = passed + len(errors)
    return dict(valid=not errors, score=round(passed/max(1,total),4), critical=bool(errors),
                errors=errors, warnings=warnings, scope="document structure / declared arithmetic / quote provenance only",
                scientific_validity="not experimentally tested", adoptable=False)


def assess(source, artifact):
    try:
        data = read(artifact)
        if not isinstance(data, dict):raise ValueError("method artifact must be an object")
        return inspect_artifact(Path(source), data)
    except (ValueError, KeyError, TypeError, OSError, AttributeError, IndexError) as exc:
        return dict(valid=False, score=0, critical=True, errors=[str(exc)], warnings=[],
                    scope="document checks only", scientific_validity="not experimentally tested", adoptable=False)
