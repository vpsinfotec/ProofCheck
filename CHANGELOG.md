# Changelog

## 0.3.0 — 2026-09-12

### Performance

Prepared, run-scoped matching normalizes pages once and reuses repeated cells. Exact
matches avoid fuzzy scoring; snippets align only the best candidate. PDFium text
extraction is restored. OCR uses bounded batches, a process-wide native lock, blank-page
shortcuts, subprocess timeouts, and an OpenMP thread limit. The UI renders 100 results
at once and debounces search. Stage timings are available in check responses.

### Correctness and edge cases

Correct Unicode snippet spans, deterministic ties, unrounded threshold comparison,
normalized-empty handling, and short-fragment score penalties. Spreadsheet validation
rejects ambiguous headers, oversized dimensions, empty selections/data, and expanded ZIPs.
Report text cannot become Excel formulas; sheet names are sanitized and deduplicated.
Image orientation is applied and unsupported multi-frame input is explicitly reported.
Cache corruption is a miss, failed OCR is retryable, writes are atomic, and retention is bounded.
CLI inspection honors header/sheet options and protects original files from report output.

### API and frontend reliability

Blocking routes run in the threadpool. Body and admission limits precede multipart parsing.
Report downloads require ownership. Session parsing handles malformed Unicode/large tokens;
registration identity is normalized consistently. Internal error details stay on the server.
SQLite connections close deterministically. Frontend inspection uses aborts and sequence
checks; duplicate runs are prevented; route callbacks cannot mutate newer views; large
results are paginated; validation and network errors are readable.

### Delivery

Preserved the supplied staged changes as baseline commit `9c9502c`. Added descriptive
commits, Python/UI/browser regressions, benchmark scripts/evidence, updated architecture,
API/configuration/deployment documentation, and a source ZIP with Git history.
