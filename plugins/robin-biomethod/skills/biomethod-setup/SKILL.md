---
name: biomethod-setup
description: Load when the user explicitly asks to initialize RobinBioMethod, check its local prerequisites, or troubleshoot its installation. Do not run synthesis optimization or model probes during setup.
---
Resolve the plugin root two levels above this skill directory. Use scripts/biomethod.py.
Run it with Python 3.12 or 3.13. `setup` creates an independent private environment;
`doctor` checks Codex/login and optional PDF tools, without making a model request.
Do not install or upgrade system tools automatically. Explain missing dependencies.
The bundled public `demo --out <new-directory>` needs no Codex login, network or model.
Use the user's artifact location or outputs/research/<YYYY-MM>/ for deliverables.
The plugin has no implicit optimization, Notion sync, global skill replacement or
scientific adoption command. Actual `run` consumes the user's Codex allowance and needs
an explicit experiment request and bounded budget. Setup does not authorize that run.
