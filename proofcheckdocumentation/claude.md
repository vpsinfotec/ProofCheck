# Developer guide — ProofCheck 0.3.1

Read the root README and docs/ARCHITECTURE.md before changing the pipeline.

## Design invariants

- Matching and duplicate-review logic belongs in matcher/normalize/duplicates, never in API/CLI/UI glue.
- CLI and API call pipeline.run and consume the same RunResult.
- A PreparedMatcher is per run; do not persist its values across users.
- Preserve deterministic page ordering and independent per-row diff and review lists.
- Duplicate review must inspect later pages without changing similarity verdicts; old history is unaudited, not zero findings.
- All native PDFium calls and object destruction hold PDFIUM_LOCK.
- Do not render every OCR page in memory before processing; preserve bounded batches.
- Upload cleanup, report ownership, and inert Excel string exports are required.
- Treat filenames, report contents, and OCR cache text as potentially sensitive.
- UI async replies must be scoped to the view and inspection sequence that created them.
- Do not bypass runtime limits or silently change matching semantics for performance.

## Verification

Python: python -m pytest -q. UI: npm ci && npm run test:ui.
Browser: install Playwright Chromium, then npm run test:browser.
Benchmarks: python scripts/benchmarks/processing.py (local baseline history required).

The audit, known boundaries, measurements, API contract, and settings live in root docs/.
Keep those documents and relevant module notes aligned with behavior changes. Commit major
changes separately with descriptive messages. Runtime dependencies, temporary reports, OCR
cache, credentials, and installed environments must not be committed.

No hosted deployment was performed for this release. Optional Tesseract OCR uses learned
recognition models locally; do not claim that the OCR path contains no machine learning.
