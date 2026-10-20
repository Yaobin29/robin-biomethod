"""Material-neutral preparation and explicit Harness2 dimension lenses."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
from robinharness.runtime import dump, fingerprint, safe_relative

PLUGIN = Path(__file__).resolve().parents[2]
INV = """Trace the earliest observed process failure. Verify full-text and supplements coverage,
source locators and quote fidelity; reconcile units and recompute declared calculations;
enumerate missing inputs and constraints before drafting. Preserve route identity and reopen
all deliverables. Sources, goal and controller checks are immutable. Do not solve chemistry
or add material-specific facts in INV. No extra requirements without trajectory evidence."""
DOM = """Apply only this task's supplied material profile and evidence. Separate observed results,
reported protocol, extrapolations and new experimental proposals. Check material identity,
reaction/processing mechanism, parameter dependencies, measurement definitions and scope of
transfer. Never copy a parameter from one route into another as a reported condition. Identify
missing causal evidence and design the smallest experiment that can falsify the main assumption.
Keep independent synthesis batches distinct from technical measurements. Do not equate a paper's
reported yield/property with a guaranteed outcome in a new batch. No preset material or universal
numerical recipe. Evidence must remain in source/ rather than become durable harness facts."""
YARDSTICK = """Deliver candidate methods AND discriminating validation experiments. Preserve
uncertainty, parameter provenance and route compatibility. AGG may merge justified RULE edits,
adopt one or KEEP_BASE; it must not splice incompatible recipes. Retain multiple methods when
evidence cannot select one. Source/goal constraints and evaluator are not editable. Document
checks do not prove reaction performance, purity, biocompatibility or achieved target values."""


def read(path):
    return json.loads(Path(path).read_text())


def validate_goal(goal):
    if not isinstance(goal, dict) or goal.get("schema_version") != 1:
        raise ValueError("Goal schema_version must be 1.")
    for key in ("material", "application"):
        if not isinstance(goal.get(key), str) or not goal[key].strip():
            raise ValueError(f"Goal needs {key}.")
    target = goal.get("target", {})
    if not isinstance(target, dict):
        raise ValueError("Goal target must be an object.")
    for key in ("metric", "definition", "assay", "unit"):
        if not isinstance(target.get(key), str) or not target[key].strip():
            raise ValueError(f"Clarify target.{key} before preparation.")
    for key in ("value", "tolerance"):
        if not isinstance(target.get(key), (int, float)) or isinstance(target[key], bool) or not math.isfinite(target[key]):
            raise ValueError(f"target.{key} must be numeric.")
    if target["tolerance"] < 0:
        raise ValueError("Target tolerance cannot be negative.")
    scale = goal.get("scale", {})
    if not isinstance(scale, dict) or not isinstance(scale.get("value"), (int, float)) or isinstance(scale["value"], bool) or not math.isfinite(scale["value"]) or scale["value"] <= 0 or not scale.get("unit") or not scale.get("basis"):
        raise ValueError("Specify positive scale.value, unit and basis.")
    if not isinstance(goal.get("constraints"), list) or not isinstance(goal.get("available_equipment"), list):
        raise ValueError("Specify constraints and available_equipment arrays (empty is allowed).")
    ids = []
    for c in goal["constraints"]:
        if not isinstance(c, dict) or c.get("kind") not in ("hard", "preference") or not c.get("id") or not c.get("description"):
            raise ValueError("Each constraint needs id, kind and description.")
        ids.append(c["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate constraint id.")


def source_index(source):
    registry = read(source / "registry.json")
    docs, lines = {}, {}
    for doc in registry.get("documents", []):
        did = doc["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", did) or did in docs:
            raise ValueError("Invalid or duplicate source id.")
        p = source / safe_relative(doc["text_file"])
        if doc.get("access") not in ("full_text", "user_supplied_full_text", "curated_excerpt"):
            raise ValueError("Abstract-only sources cannot supply method evidence.")
        if hashlib.sha256(p.read_bytes()).hexdigest() != doc["sha256"]:
            raise ValueError("Evidence document hash mismatch: " + did)
        if not doc.get("title") or not doc.get("url"):
            raise ValueError("Source needs title and stable URL.")
        docs[did] = doc
        for line in p.read_text().splitlines():
            m = re.match(r"\[([^\]]+)\]\s*(.*)", line)
            if m:
                k = (did, m[1])
                if k in lines:
                    raise ValueError("Duplicate source locator.")
                lines[k] = m[2]
    if not docs or not lines:
        raise ValueError("No locatable full-text evidence.")
    return docs, lines


def check_cites(cites, docs, lines):
    if not isinstance(cites, list) or not cites:
        return False
    return all(isinstance(c, dict) and c.get("document") in docs and
               isinstance(c.get("quote"), str) and bool(c["quote"].strip()) and
               c["quote"] in lines.get((c.get("document"), c.get("locator")), "") for c in cites)


def validate_task_source(source):
    fingerprint(source)
    goal = read(source / "goal.json");validate_goal(goal)
    docs, lines = source_index(source)
    cards = read(source / "method_cards.json")
    if not isinstance(cards, list) or not cards:
        raise ValueError("Extract at least one method card before preparing the task.")
    ids = set()
    for card in cards:
        if not isinstance(card, dict) or not card.get("id") or card["id"] in ids or card.get("document") not in docs or not card.get("name"):
            raise ValueError("Invalid method card/route identity.")
        ids.add(card["id"])
        if not isinstance(card.get("parameters"), list) or not card["parameters"] or not isinstance(card.get("limitations"), list):
            raise ValueError("Method cards require parameters and explicit limitations.")
        for param in card["parameters"]:
            if not isinstance(param, dict) or not param.get("name") or "unit" not in param:
                raise ValueError("Invalid method parameter.")
            if param.get("value") is not None and not check_cites(param.get("evidence"), docs, lines):
                raise ValueError("Method-card parameter needs locatable source evidence.")
            if param.get("value") is not None and any(c.get("document") != card["document"] for c in param["evidence"]):
                raise ValueError("Method card parameters must retain their route document.")
            if param.get("value") is None and not param.get("missing_reason"):
                raise ValueError("Unknown method parameter needs missing_reason.")
    profile = read(source / "profile.json")
    if not isinstance(profile, dict) or not isinstance(profile.get("checks"), list):
        raise ValueError("Material profile requires a checks array.")
    return goal, docs, cards, profile


def prompt_lenses(source):
    goal, _, _, profile = validate_task_source(source)
    return dict(inv_levers=INV, dom_levers=DOM,
                yardstick=YARDSTICK, domain_guidance="Read source/goal.json, registry.json, method_cards.json and profile.json. "
                + "Material for this task: " + goal["material"] + ". Material-scoped checks: " + json.dumps(profile["checks"], ensure_ascii=False),
                selection_checks="Choose a useful source-grounded deliverable, not the longest one. Do not reward invented parameters or certainty. Evaluate methods and validation experiments together.")


def prepare(goal_path, bundle, cards_path, out, profile_path=None):
    if out.exists():
        raise ValueError("Use a new task output directory.")
    validate_goal(read(goal_path))
    fingerprint(bundle)
    # Only registered documents are imported; arbitrary bundle files never enter workers.
    docs, _ = source_index(bundle)
    out.mkdir(parents=True)
    source = out / "source";source.mkdir()
    shutil.copy2(bundle / "registry.json", source / "registry.json")
    for doc in docs.values():
        dest = source / safe_relative(doc["text_file"]);dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundle / doc["text_file"], dest)
    shutil.copy2(goal_path, source / "goal.json")
    shutil.copy2(cards_path, source / "method_cards.json")
    dump(source / "profile.json", read(profile_path or PLUGIN / "assets/generic-profile.json"))
    validate_task_source(source)
    shutil.copytree(PLUGIN / "assets/base", out / "base")
    shutil.copy2(PLUGIN / "assets/task-prompt.txt", out / "prompt.txt")
    slug = re.sub(r"[^a-z0-9]+", "-", read(goal_path)["material"].lower()).strip("-") or "material"
    digest = fingerprint(source)
    dump(out / "task.json", dict(id=slug + "-" + digest[:10], domain="biomaterial-synthesis/" + slug,
         work="design evidence-grounded biomaterial synthesis methods AND minimal discriminating validation experiments",
         prompt_file="prompt.txt", source_dir="source", base_harness="base", output="method.json", evaluator="biomethod-v1"))
    dump(out / "preparation.json", dict(source_hash=digest, status="prepared", model_calls=0,
         evidence_scope="closed supplied source set; public search provenance only when registry.search is supplied"))
    return dict(status="prepared", task=str(out / "task.json"), source_hash=digest, model_calls=0)
