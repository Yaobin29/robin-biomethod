# Validation — RobinBioMethod 0.1.0

Date:2026-10-20. Independent implementation, not a Google or OpenAI benchmark result.

| Boundary | Result |
| --- | --- |
| macOS Python3.12 | 62 offline tests passed |
| macOS Python3.13 | 62 offline tests passed |
| Native Codex plugin installation | Passed on CLI0.147.0 |
| Skill discovery | biomethod-setup and biomethod-design found in model-visible prompt input |
| Clean ZIP install in isolated home / path with spaces | Passed |
| Public search | Europe PMC PubMed subset returned the expected DOI/PMCID |
| Public full-text collection | Two selected open-access GelMA articles retrieved through Europe PMC |
| Public example | Curated method JSON, document assessment and rendered method/experiments delivered |
| Original Harness2 INV/DOM, AGG and selection | Offline scripted integration: k1 and k2 passed |
| Material-neutral routing | Synthetic second-material fixture passed; not chemical-transfer evidence |
| Additional model sessions | ZERO; no real INV/DOM optimization was claimed |
| Wet-lab validation / synthesis improvement | Not performed / not established |
| Linux | CI configured, not run |
| Public repository | https://github.com/Yaobin29/robin-biomethod |

The62tests comprise28inherited runtime/core tests and34product tests, covering provenance,
route identity, source drift, target/constraint handling, calculation errors, invalid quotes,
missing uncertainty experiments, controls/batches, search/collection failure, source merging,
reporting and original-core wiring. Scripted outputs do not prove reasoning capability.
A dedicated test confirms improved document scores still cannot enable scientific adoption.

The example is intentionally incomplete as a lab procedure. Target70±5% primary-amine
conversion and5g precursor are a hypothetical intake, not a result reported by the sources.
The two selected papers use different gelatin types and conditions. The TFF route is
reference-only under the example's equipment constraint. Purification details, source
coverage, assay normalization and target-feed calibration require further work.
The delivered experiment maps these uncertainties to controls and observable outcomes;
its proposed pilot counts are not a powered efficacy or reproducibility study.

Controller checks verify structure, frozen-card consistency, exact quote provenance and
declared arithmetic. They cannot establish chemical entailment, dimensionally valid
scaling assumptions, assay specificity, hazards, purity, cell compatibility or target success.
Human scientific review and experiments are required. No adopt command is exposed.

No personal Notion database, credential, private paper, global skill package or GelMA
dialysis calculator was included. Public excerpts retain CC BY4.0 attribution in NOTICE.
Optional Zotero/OpenDataLoader backends were not exercised; text input remains standalone.
The original Robinharness source, global model configuration and governance were not edited.
