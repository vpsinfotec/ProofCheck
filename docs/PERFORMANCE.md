# Performance evidence

The provided archive baseline is commit `9c9502c`. It included staged changes that were
committed unchanged before the audit. Measurements below compare that baseline's matching
and extraction code against the updated pipeline on the same local environment. These
measurements were rerun for 0.3.1 with duplicate review enabled, including all-page
occurrence counting and repeated-word indexing. They supersede the 0.3.0 timings.

| Synthetic workload | Values | Pages | Baseline median | Updated median | Speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| exact_unique | 300 | 20 | 0.1815 s | 0.0106 s | 17.1× |
| exact_repeated | 600 | 20 | 0.3391 s | 0.0038 s | 88.7× |
| fuzzy_and_missing | 80 | 20 | 0.0523 s | 0.0175 s | 3.0× |
| duplicate_names | 600 | 20 | 0.4076 s | 0.0069 s | 59.5× |
| pipeline_text_pdf | 600 | 20 | 0.8135 s | 0.0393 s | 20.7× |

Three repetitions per variant, measured with `perf_counter`; Python 3.12.14 on
Linux. All comparison workloads retained expected value, status, page, and integer score.
These fixtures do not exercise the intentionally corrected empty/threshold/short-fragment
edge cases. Diff/snippet behavior was checked separately by regression tests.

`exact_unique` uses 300 distinct values. `exact_repeated` uses 600 cells but only 30 distinct
values. The mixed workload has 50 near-miss names and 30 missing values. The pipeline fixture
creates a real 600-row Excel workbook and a 20-page text PDF. Matching-only tests exclude
input parsing; pipeline tests include workbook loading, extraction, and matching but exclude
uploads, HTTP JSON serialization, browser rendering, and report generation. The
`duplicate_names` workload has 600 cells, 30 distinct names, 40 occurrences per name
across 20 pages, and a repeated-word finding on every page; all counts and review flags
are asserted as well as baseline verdict parity. The API's own
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
Duplicate review scans all normalized pages even after an exact hit, adding work relative
to the 0.3.0 early-return path. The repeated-word index is prepared once, occurrence output
is aggregated per page, and repeated cells reuse both their verdict and review evidence.

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
