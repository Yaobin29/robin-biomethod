#!/usr/bin/env python3
"""Build a source-only, reproducible ZIP; never include runtime state or credentials."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {".agents", ".github", "plugins", "scripts"}
FILES = {"README.md", "README.zh-CN.md", "LICENSE", "VALIDATION.md", "CHANGELOG.md", ".gitignore"}


def build(destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    version = json.loads((ROOT / "plugins/robin-biomethod/plugin.json").read_text())["version"]
    archive = destination / f"robin-biomethod-{version}.zip"
    paths = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(ROOT)
        if rel.parts[0] not in ALLOWED and str(rel) not in FILES:
            continue
        if any(x in rel.parts for x in ("__pycache__", ".git", "runs", "local-runtime", ".venv")):
            continue
        if p.suffix in (".pyc", ".zip") or p.name in (".env", "auth.json"):
            continue
        content = p.read_bytes()
        private_root = b"/" + b"Users" + b"/"
        if private_root in content:
            raise ValueError(f"Private machine path in release file: {rel}")
        if (b'"access_' + b'token":') in content or (b'"refresh_' + b'token":') in content:
            raise ValueError(f"Credential material in release file: {rel}")
        paths.append((rel, content))
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, content in paths:
            name = f"robin-biomethod-{version}/{rel.as_posix()}"
            info = zipfile.ZipInfo(name, (2026, 10, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, content)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (destination / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n")
    return dict(archive=str(archive), files=len(paths), sha256=digest)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    print(json.dumps(build(p.parse_args().output), indent=2))
