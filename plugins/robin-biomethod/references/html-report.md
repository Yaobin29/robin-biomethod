# Offline scientific HTML reports

The primary final document is `report.html`. Default design, final-only recovery and
post-core contract repair all export it. Markdown, structured JSON and original audit
traces remain available. Existing jobs can be rendered without another model call:

    python3 scripts/biomethod.py html-report /path/to/job

For a standalone artifact use `render --task TASK --artifact METHOD --out method.html`.
An explicit `.md` suffix retains the previous Markdown renderer. `demo` writes both
`method.html` and `method.md`, and always says it is curated, not a full workflow.

## Design contract

- Editorial scientific dossier: warm paper, ink typography, one teal accent, numbered
  sections, desktop contents and responsive mobile navigation. Adapted from the local
  frontend-design and frontend-skill design principles; no external skills are required.
- One offline file; CSS is inline. No JavaScript, tracking, external fonts, CDN or assets.
- Browser print support, keyboard navigation, native disclosure panels, reduced motion,
  accessible tables and explicit unknowns. The report is readable without animations.
- Report order: design brief, literature 3W, actual stages and rule decisions, candidate
  methods, discriminating experiments, uncertainties, sources and document checks.
- All source content is escaped; links allow only HTTP(S). A restrictive CSP blocks
  scripts and external resources. Reports can still contain private scientific inputs:
  keep generated user reports outside public release bundles.
- Saved jobs recheck execution evidence. A standalone render never asserts execution.
  Core-execution checks, document validity and experimental validation are separate.
- Stage details embed actual candidate methods when available, so the single file does
  not depend on local method links. Missing stage files stay visibly missing.
- Usage is explicitly scoped to the recorded job budget, not an invented total across
  earlier jobs. Rendering neither consumes nor silently renews the model budget.

## Presentation regression cases

Positive: completed job has 3W, actual stages, rules, method parameters, falsifiable
experiments and citations. Negative: curated output cannot claim real core execution;
HTML and malicious URL source strings cannot execute. Boundary: null tolerance remains
unknown, missing source/stage records remain missing, explicit Markdown stays compatible.

Visual styling can change without altering scientific values or rewriting stage outputs.
The renderer is a deterministic package capability, rather than a general design skill
copied into every model prompt. Slide themes from html-ppt are deliberately not required
for the scrollable scientific report.
