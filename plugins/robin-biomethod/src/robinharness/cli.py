"""Small CLI used by the bundled Codex skills."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import difflib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import venv

from . import __version__
from .runtime import Budget, CodexRunner, POLICY, dump, fingerprint, state_root
from .engine import CodexProposer, FileTaskAdapter, evaluate, run_task
from .adoption import adopt, rollback

PLUGIN = Path(__file__).resolve().parents[2]


def doctor(smoke=False, root=None, model=None):
    codex = shutil.which("codex")
    payload = dict(version=__version__, python=sys.version.split()[0],
                   supported_python=(3, 12) <= sys.version_info[:2] < (3, 14),
                   platform=sys.platform, codex=bool(codex), login=False,
                   plugin_root=str(PLUGIN), smoke="not_run")
    auth_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    payload["file_backed_login"] = (auth_home / "auth.json").is_file()
    payload["requested_model"] = model or "codex-default"
    payload["supported_codex"] = False
    if codex:
        p = subprocess.run([codex, "--version"], capture_output=True, text=True, timeout=15)
        payload["codex_version"] = p.stdout.strip()
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", p.stdout)
        payload["supported_codex"] = bool(match and tuple(map(int, match.groups())) >= (0, 147, 0))
        p = subprocess.run([codex, "login", "status"], capture_output=True, text=True, timeout=15)
        payload["login"] = p.returncode == 0
    payload["ok"] = (payload["supported_python"] and payload["supported_codex"]
                     and payload["login"] and payload["file_backed_login"])
    if smoke and payload["ok"]:
        rd = root or state_root() / "smoke" / str(time.time_ns())
        budget = Budget(rd / "budget.json", max_sessions=1, minutes=3)
        runner = CodexRunner(budget, rd / "audit", model)
        with tempfile.TemporaryDirectory(prefix="robinharness-smoke-") as td:
            ws = Path(td)
            (ws / "AGENTS.md").write_text(POLICY)
            result = runner.run(ws, "Do not use tools. Reply with exactly ROBINHARNESS_READY.", "smoke")
            payload["smoke"] = "passed" if result["text"].strip() == "ROBINHARNESS_READY" else "failed"
            payload["ok"] = payload["smoke"] == "passed"
        payload["record"] = str(rd)
    return payload


def setup():
    if not (3, 12) <= sys.version_info[:2] < (3, 14):
        raise ValueError("Use Python 3.12 or 3.13. No system packages were changed.")
    home = state_root()
    env = home / "venv"
    if not (env / "bin/python").exists():
        venv.EnvBuilder(with_pip=False).create(env)
    dump(home / "installation.json", dict(version=__version__, plugin_root=str(PLUGIN),
         upstream=json.loads((PLUGIN / "vendor/UPSTREAM.json").read_text())["commit"]))
    return dict(ok=True, python=str(env / "bin/python"), state=str(home),
                next="Run doctor --smoke, then run --task <task.json>.")


def read_report(run: Path):
    if (run / "report.json").is_file():
        return json.loads((run / "report.json").read_text())
    if (run / "budget.json").is_file():
        budget = json.loads((run / "budget.json").read_text())
        return dict(status="not_finalized", meaning="in progress or interrupted",
                    elapsed_s=round(time.time() - budget["started"], 1),
                    sessions=budget["sessions"], max_sessions=budget["max_sessions"],
                    report_available=False)
    raise ValueError("No experiment report or budget exists in this directory.")


def config_diff(base, candidate):
    out = []
    for name in sorted(set(p.relative_to(base) for p in base.rglob("*") if p.is_file()) |
                       set(p.relative_to(candidate) for p in candidate.rglob("*") if p.is_file())):
        a, b = base / name, candidate / name
        out.extend(difflib.unified_diff(a.read_text().splitlines(True) if a.exists() else [],
                   b.read_text().splitlines(True) if b.exists() else [],
                   fromfile="base/" + str(name), tofile="candidate/" + str(name)))
    return "".join(out)


def unknown_costs(value):
    """Upstream float defaults are placeholders, not measured monetary costs."""
    if isinstance(value, dict):
        return {k: None if k in ("usd", "cost_usd", "rollout_usd", "session_usd") else unknown_costs(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [unknown_costs(v) for v in value]
    return value


def snapshot_task(adapter, dest: Path) -> Path:
    """Freeze supplied task, prompt, baseline and controller-only expectations."""
    dest.mkdir(parents=True, exist_ok=False)
    shutil.copytree(adapter.base, dest / "base")
    shutil.copytree(adapter.source, dest / "source")
    (dest / "prompt.txt").write_text(adapter.task_prompt(adapter.task_id))
    definition = dict(adapter.task, base_harness="base", source_dir="source", prompt_file="prompt.txt")
    dump(dest / "task.json", definition)
    expected = adapter.manifest.parent / "expected.json"
    if expected.exists():
        shutil.copy2(expected, dest / "expected.json")
    return dest / "task.json"


def optimize(args):
    if not (1 <= args.k <= 3) or not (1 <= args.session_limit <= 24) or not (1 <= args.minutes <= 60):
        raise ValueError("v0.1 limits: k=1..3, sessions=1..24, minutes=1..60.")
    source_manifest = Path(args.task).expanduser().resolve()
    run = (Path(args.run_dir).expanduser().resolve() if args.run_dir else
           state_root() / "runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    if (run / "report.json").exists() or (run / "budget.json").exists():
        raise ValueError("Use a new run directory. v0.1 does not resume partially evaluated runs.")
    run.mkdir(parents=True, exist_ok=False)
    budget = Budget(run / "budget.json", args.session_limit, args.minutes)
    runner = CodexRunner(budget, run / "audit", args.model)
    proposer = CodexProposer(runner, run / "editors")
    original = FileTaskAdapter(source_manifest, run / "primary", runner)
    original_base_hash = fingerprint(original.base)
    used = {fingerprint(original.source)}
    ids = {original.task_id}
    holdouts = []
    for i, path in enumerate(args.holdout):
        held = FileTaskAdapter(Path(path).resolve(), run / "heldout" / str(i), runner)
        digest = fingerprint(held.source)
        if digest in used or held.task_id in ids:
            raise ValueError("Holdouts must have distinct task ids and source snapshots.")
        used.add(digest)
        ids.add(held.task_id)
        holdouts.append(held)
    later = None
    if args.learning_task:
        later = FileTaskAdapter(Path(args.learning_task).resolve(), run / "later", runner)
        if fingerprint(later.source) in used or later.task_id in ids:
            raise ValueError("The later adaptation must not reuse adaptation or holdout inputs.")
    # Snapshot explicitly declared task inputs; evaluation data stays controller-side.
    frozen_manifest = snapshot_task(original, run / "frozen")
    held_manifests = [snapshot_task(h, run / "inputs" / f"heldout-{i}") for i, h in enumerate(holdouts)]
    later_manifest = snapshot_task(later, run / "inputs" / "later") if later else None
    adapter = FileTaskAdapter(frozen_manifest, run / "primary", runner)
    library_root = run / "library"
    seed_library = getattr(args, "library_dir", None)
    if seed_library:
        from harness2.core.library import Library
        source_library = Path(seed_library).expanduser().resolve()
        fingerprint(source_library)
        if not source_library.is_dir():
            raise ValueError("The seed library must be an existing directory.")
        shutil.copytree(source_library, library_root)
        # Never seed an experiment with an entry from its own tasks or holdouts.
        excluded = list(ids) + ([later.task_id] if later else [])
        Library(library_root, adapter.domain_of(adapter.task_id),
                adapter.substrate.surface()).forget(excluded)
    report = dict(version=__version__, status="running", model=runner.model,
                  task=adapter.task_id, base_hash=original_base_hash,
                  original_base=str(original.base), candidate=None, adopted=False,
                  recommended=False, evaluations=[], errors=[],
                  upstream=json.loads((PLUGIN / "vendor/UPSTREAM.json").read_text())["commit"],
                  seed_library=str(source_library) if seed_library else None,
                  method=dict(k=args.k, mode=args.mode), performance_claim="not established")
    try:
        result = run_task(adapter, proposer, k=args.k, mode=args.mode, library_root=library_root)
        report["upstream_result"] = unknown_costs(result.to_dict())
        if result.status != "ok":
            raise RuntimeError("Upstream task incomplete: " + "; ".join(result.errors))
        token = "agg" if args.mode == "parallel" else "seq"
        chosen = result.selections[token]["chosen_label"]
        summary = next((adapter.root / "runs").rglob("summary.json"))
        candidate = summary.parent / "harnesses" / chosen
        report["candidate"] = str(candidate)
        report["candidate_hash"] = fingerprint(candidate)
        (run / "changes.diff").write_text(config_diff(adapter.base, candidate))
        base_run = Path(result.base[0]["run_dir"])
        selected_run = Path(result.selections[token]["chosen_run_dir"])
        report["evaluations"].append(dict(task=adapter.task_id, split="adaptation",
                  base=evaluate(adapter, base_run), candidate=evaluate(adapter, selected_run)))
        # Freeze the selected candidate before any held-out task is executed.
        for i, path in enumerate(held_manifests):
            h = FileTaskAdapter(Path(path).resolve(), run / "heldout" / str(i), runner)
            b = h.execute(h.task_id, adapter.base, "baseline")
            c = h.execute(h.task_id, candidate, "candidate")
            report["evaluations"].append(dict(task=h.task_id, split="heldout",
                         base=evaluate(h, b), candidate=evaluate(h, c)))
        if later_manifest:
            later = FileTaskAdapter(later_manifest, run / "later", runner)
            later_result = run_task(later, proposer, k=args.k, mode=args.mode,
                                    library_root=library_root)
            report["later_task_status"] = later_result.status
            report["later_task"] = unknown_costs(later_result.to_dict())
            if later_result.status != "ok":
                raise RuntimeError("Later adaptation task incomplete.")
        held = [x for x in report["evaluations"] if x["split"] == "heldout"]
        report["recommended"] = bool(held) and all(
            not x["candidate"]["critical"] and x["candidate"]["valid"] and
            x["candidate"]["score"] >= x["base"]["score"] for x in held
        ) and any(x["candidate"]["score"] > x["base"]["score"] for x in held)
        if adapter.task.get("evaluator") == "biomethod-v1":
            report["document_quality_improvement"] = report["recommended"]
            report["recommended"] = False
            report["scientific_performance"] = "not experimentally tested"
        report["status"] = "completed"
        report["performance_claim"] = "small-sample improvement" if report["recommended"] else "no demonstrated held-out improvement"
    except Exception as exc:
        report["status"] = "incomplete"
        report["errors"].append(str(exc))
    finally:
        report["budget"] = json.loads(budget.path.read_text())
        report["original_unchanged"] = fingerprint(original.base) == original_base_hash
        dump(run / "report.json", report)
    return report, run


def main(argv=None):
    p = argparse.ArgumentParser(prog="robinharness")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("setup")
    d = sub.add_parser("doctor")
    d.add_argument("--smoke", action="store_true")
    d.add_argument("--model")
    d.add_argument("--run-dir", type=Path)
    r = sub.add_parser("run")
    r.add_argument("--task", required=True)
    r.add_argument("--holdout", action="append", default=[])
    r.add_argument("--learning-task")
    r.add_argument("--library-dir", help="Explicitly seed from a previous experiment library; the source is never modified.")
    r.add_argument("--model")
    r.add_argument("--k", type=int, default=1)
    r.add_argument("--mode", choices=["parallel", "sequential"], default="parallel")
    r.add_argument("--session-limit", type=int, default=24)
    r.add_argument("--minutes", type=int, default=60)
    r.add_argument("--run-dir")
    s = sub.add_parser("report")
    s.add_argument("run_dir", type=Path)
    a = sub.add_parser("adopt")
    a.add_argument("run_dir", type=Path)
    a.add_argument("--target", type=Path, required=True)
    a.add_argument("--confirmed", action="store_true")
    b = sub.add_parser("rollback")
    b.add_argument("transaction", type=Path)
    b.add_argument("--confirmed", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.command == "setup":
            out = setup()
        elif args.command == "doctor":
            out = doctor(args.smoke, args.run_dir, args.model)
        elif args.command == "run":
            report, run = optimize(args)
            out = dict(status=report["status"], recommended=report["recommended"], report=str(run / "report.json"),
                       errors=report["errors"])
        elif args.command == "report":
            out = read_report(args.run_dir)
        elif args.command == "adopt":
            report = json.loads((args.run_dir / "report.json").read_text())
            if not args.confirmed:
                raise ValueError("Explicit user confirmation is required before adopt.")
            if not report["recommended"] or report["status"] != "completed":
                raise ValueError("No validated held-out improvement; keep the original.")
            candidate = Path(report["candidate"])
            if fingerprint(candidate) != report["candidate_hash"]:
                raise ValueError("Candidate changed after evaluation.")
            if args.target.resolve() != Path(report["original_base"]).resolve():
                raise ValueError("Target must be the exact reviewed task-harness directory.")
            txn = adopt(candidate, args.target, state_root(), report["base_hash"])
            out = dict(ok=True, transaction=str(txn))
        elif args.command == "rollback":
            if not args.confirmed:
                raise ValueError("Explicit user confirmation is required before rollback.")
            rollback(args.transaction)
            out = dict(ok=True)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out.get("ok", True) and out.get("status") != "incomplete" else 1
    except Exception as exc:
        print(json.dumps(dict(ok=False, error=str(exc)), ensure_ascii=False), file=sys.stderr)
        return 1
