"""Explicit, hash-guarded adoption; never overwrite installed plugin caches."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import time
from .runtime import dump, fingerprint
from .engine import validate_config, Surface
from harness2.core import tree


def adopt(candidate: Path, target: Path, state: Path, expected_hash: str) -> Path:
    candidate, target, state = candidate.resolve(), target.absolute(), state.resolve()
    if target.is_symlink() or not target.is_dir():
        raise ValueError("Target must be an existing, real task-harness directory.")
    if target.resolve() in candidate.parents or candidate in target.resolve().parents:
        raise ValueError("Candidate and target must be separate trees.")
    if any(p.is_symlink() for p in target.rglob("*")):
        raise ValueError("Target contains symlinks.")
    if fingerprint(target) != expected_hash:
        raise ValueError("Target changed since the user reviewed it; refusing adoption.")
    forbidden = {Path.home() / ".codex", Path.home() / ".agents"}
    if any(target.resolve() == p or p in target.resolve().parents for p in forbidden):
        raise ValueError("Global Codex configuration is not an adoption target.")
    if ".codex/plugins" in str(target):
        raise ValueError("Plugin caches are immutable; export to a project task harness.")
    config = tree.read_tree(Surface().surface(), candidate)
    validate_config(config)
    # No hidden off-surface files can be smuggled into an adopted harness.
    if set(config) != {p.relative_to(candidate).as_posix() for p in candidate.rglob("*") if p.is_file()}:
        raise ValueError("Candidate contains off-surface files.")
    txn = state / "backups" / f"{time.time_ns()}"
    shutil.copytree(target, txn / "before")
    dump(txn / "transaction.json", dict(target=str(target), before=expected_hash,
                                      after=fingerprint(candidate), state="prepared"))
    with tempfile.TemporaryDirectory(prefix=".robinharness-adopt-", dir=target.parent) as td:
        staged = Path(td) / "new"
        shutil.copytree(candidate, staged)
        old = Path(td) / "old"
        target.rename(old)
        try:
            staged.rename(target)
        except Exception:
            old.rename(target)
            raise
    record = json.loads((txn / "transaction.json").read_text())
    record["state"] = "adopted"
    dump(txn / "transaction.json", record)
    return txn


def rollback(transaction: Path):
    record = json.loads((transaction / "transaction.json").read_text())
    target = Path(record["target"])
    if record["state"] != "adopted" or fingerprint(target) != record["after"]:
        raise ValueError("Target changed after adoption; refusing to overwrite newer work.")
    if fingerprint(transaction / "before") != record["before"]:
        raise ValueError("Backup integrity check failed.")
    with tempfile.TemporaryDirectory(prefix=".robinharness-rollback-", dir=target.parent) as td:
        saved = Path(td) / "saved"
        shutil.copytree(transaction / "before", saved)
        target.rename(Path(td) / "current")
        saved.rename(target)
    record["state"] = "rolled_back"
    dump(transaction / "transaction.json", record)
