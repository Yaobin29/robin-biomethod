---
name: biomethod-setup
description: Load when the user wants to install, initialize or diagnose RobinBioMethod. If the same request asks to design a hydrogel or biomaterial method, hand off to biomethod-design after basic checks rather than stopping at setup.
---
Resolve plugin root two levels above this directory. Use scripts/biomethod.py with Python3.12/3.13.
`setup` creates private state and shows budget settings. `doctor` checks local prerequisites;
it is not proof of model access or workflow execution. Do not upgrade system packages automatically.

If the request is setup/install only, stop after those checks; no model calls are authorized.
If the user also asks for synthesis, hydrogel design or material construction, read sibling
../biomethod-design/SKILL.md and continue its DEFAULT FULL-HARNESS workflow. Clicking setup
must not cause the design request to become ordinary chat advice. No need for the user to
repeat the same design request or know the underlying command names.

The offline demo is only for an explicit demo request; clearly label zero model calls.
Private state and data survive updates. Do not replace global skills or publish user materials.
