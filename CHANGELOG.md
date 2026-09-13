# Changelog

## 0.3.2 — 2026-09-13

Fix startup with `MAX_UPLOAD_MB` above 5120 by raising its configurable ceiling to 10240
MiB (10 GiB). Keep the 50 MiB default and all streamed/per-file enforcement. Add four
fresh-process regressions for default, 6 GiB, 10 GiB, and above-ceiling configuration,
including health propagation and aggregate length checks beyond 32-bit sizes. Document
Windows launch commands, stale-install diagnosis, temporary disk requirements, and the
distinction between upload admission and unvalidated multi-gigabyte processing capacity.

## 0.3.1 — 2026-09-13

### Duplicate-name review

Detect adjacent repeated words in spreadsheet values and matching document text, including
repeated first, middle, and last words. Count full-value occurrences on the same and
different pages, even after an earlier exact hit. Normalize once, reuse review results
for repeated cells, avoid counting longer-word prefixes, and deduplicate overlapping
forward/reverse occurrences. Keep existing similarity verdicts and expose review evidence
separately so intentional repetition remains a human decision.

Add API occurrence/repeated-word fields, summary/history review counts, a browser review
badge and filter, and equivalent CLI/HTML/XLSX presentation. Older history has no review
count and displays Not recorded. Add 21 Python regressions plus a frontend regression and
extend live Chromium verification. Update documentation and benchmark all five workloads
with duplicate review enabled. Preserve descriptive backend/frontend/documentation commits.

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
