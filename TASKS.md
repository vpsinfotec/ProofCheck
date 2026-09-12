# Audit status — 0.3.0

Completed scope and evidence: [docs/AUDIT.md](docs/AUDIT.md).

- [x] Preserve supplied changes as a baseline commit.
- [x] Remove repeated normalization/fuzzy work and reuse repeated cells.
- [x] Restore native PDF extraction and safe bounded OCR.
- [x] Validate spreadsheet/document options and resource use.
- [x] Fix Unicode snippets, threshold/tie/empty/short-fragment edge cases.
- [x] Fix cache corruption, write races, failed-read poisoning, and retention.
- [x] Protect report ownership, spreadsheet exports, and session parsing.
- [x] Keep long checks off the event loop and reject excess work.
- [x] Fix frontend races, duplicate submissions, error display, and large result rendering.
- [x] Verify real file flow in Chromium and mobile layout.
- [x] Update documentation, benchmark evidence, and release packaging.

Explicit future work, not included in this release:

- Durable background jobs, progress polling, cancellation, and idempotent submission.
- Multi-host database/report storage and distributed admission/rate limiting.
- Revocable server-side session storage and public-service identity hardening.
- Row association, whole-word/identifier matching modes, and cross-page matches.
- Formula recalculation, displayed numeric formatting, and multi-frame image ingestion.
- Production scan corpus evaluation and deployment-specific load/capacity testing.
