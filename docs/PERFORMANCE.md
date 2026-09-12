# Performance evidence

The provided archive baseline is commit `9c9502c`. It included staged changes that were
committed unchanged before the audit. Measurements below compare that baseline's matching
and extraction code against the updated pipeline on the same local environment.

| Synthetic workload | Values | Pages | Baseline median | Updated median | Speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| exact_unique | 300 | 20 | 0.2349 s | 0.0036 s | 65.5× |
| exact_repeated | 600 | 20 | 0.5019 s | 0.0018 s | 272.3× |
| fuzzy_and_missing | 80 | 20 | 0.0749 s | 0.0193 s | 3.9× |
| pipeline_text_pdf | 600 | 20 | 1.0163 s | 0.0348 s | 29.2× |

Three repetitions per variant, measured with `perf_counter`; Python 3.12.14 on
Linux. All comparison workloads retained expected value, status, page, and integer score.
These fixtures do not exercise the intentionally corrected empty/threshold/short-fragment
edge cases. Diff/snippet behavior was checked separately by regression tests.

`exact_unique` uses 300 distinct values. `exact_repeated` uses 600 cells but only 30 distinct
values. The mixed workload has 50 near-miss names and 30 missing values. The pipeline fixture
creates a real 600-row Excel workbook and a 20-page text PDF. Matching-only tests exclude
input parsing; pipeline tests include workbook loading, extraction, and matching but exclude
uploads, HTTP JSON serialization, browser rendering, and report generation. The API's own
`timings` field additionally exposes report and server-side total duration.

Raw samples and library versions: [benchmark-results.json](benchmark-results.json).
The stored `updated_stage_seconds` describes the last repetition, not the median sample.

```bash
python scripts/benchmarks/processing.py --output docs/benchmark-results.json
```

Git history must be present to load the baseline. Benchmark code executes only tracked
Python from the explicitly named local baseline; it performs no network calls. Re-running
changes measured timings, not the workload. The script asserts verdict parity before saving.

## Why processing is faster

Previously each value normalized every page, fuzzy-scored exact matches, and repeatedly
computed alignments while searching. Now a PreparedMatcher owns normalized pages and a
run-local duplicate cache, scans exact matches first, then scores only when needed. An
alignment and original-text span map are generated only for the best fuzzy match.

The baseline had removed the native text extractor while retaining tests that expected it.
Restoring PDFium avoids Python-heavy layout analysis on the common text-layer path. Every
PDFium operation is protected by one lock; see [PDFium threading documentation](https://pypdfium2.readthedocs.io/en/stable/python_api.html#incompatibility-with-threading).

OCR has different costs and is not included in the speedup table. It now skips uniform
blank pages, limits each page's strategy time, uses bounded batches, and reuses successful
cached text. Cache state, scan quality, DPI, page dimensions, engine/language versions,
and CPU resources materially affect OCR time and accuracy. Test on your real documents.

## Remaining performance boundaries

Fuzzy search still scans all nonempty pages for every distinct unmatched value; this
preserves recall without an approximate candidate index. Character diffs and HTML/XLSX
exports can be expensive for unusually long values or large result sets. Result pagination
bounds browser DOM size, but the complete JSON result is still transferred and held in memory.

There is no durable asynchronous worker queue. API threads avoid event-loop blocking,
but native CPU/GIL work and admitted OCR can still saturate a small host. Increase limits
only after measuring representative workloads. For very long scans, split files or add
a separately designed durable queue and status protocol.
