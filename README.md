# ProofCheck 0.3.2

Check Excel values against a PDF or image, locally. The CLI and web application share
one processing pipeline and produce matching HTML, Excel, and JSON results.

Text matching uses deterministic Unicode normalization and RapidFuzz. No cloud service
or LLM is called at runtime. Optional Tesseract OCR uses trained recognition models;
OCR is not guaranteed error-free. Reproducible OCR needs the same Tesseract version,
language data, extraction engine, settings, and input. Timestamps and timings naturally vary.

## Start

Python 3.10+ is required. This release was validated on Python 3.12 / Linux.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,ocr]"
proofcheck serve --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. OCR additionally needs the Tesseract binary and installed
language packs. Existing setup scripts support Linux/macOS and Windows; see
[scripts/README.md](scripts/README.md). Containers: [DEPLOYMENT.md](DEPLOYMENT.md).

## Use the web app

1. Choose an `.xlsx` or `.xlsm` file, or drag/paste files into the panel.
2. Set the header row if it is not row 1. Wait for inspection to finish.
3. Select a sheet and columns, or enable **Check all columns**.
4. Choose a PDF or single-frame PNG/JPEG/TIFF/BMP/WebP/GIF.
5. Adjust matching options; enable OCR for scanned PDF pages if needed. Image input
   always requires OCR, regardless of the PDF OCR checkbox.
6. Run the check. Elapsed time is shown while it runs. Results are searchable and
   paginated in groups of 100; downloadable reports contain every result.

Only one check can be submitted at a time from the UI. Inputs are locked during a run.
Navigation within the app is safe; the result remains available when returning to Check.
A full browser reload loses the in-memory result and form. Completed summaries remain
in History, with report links while the files are retained. There is no background job
queue or durable status/resume endpoint in this release.

## CLI

```bash
proofcheck inspect delegates.xlsx --sheet Delegates --header-row 2
proofcheck check delegates.xlsx program.pdf --column Name --column City --reverse \
  --html result.html --xlsx result.xlsx
proofcheck check delegates.xlsx scans/ --all-columns --ocr-lang eng
proofcheck check delegates.xlsx program.pdf --column Name --ocr --ocr-dpi 200
proofcheck ocr program.pdf --pages 1,3-5 --save-images diagnostics/
```

`check` exits 0 with no missing values, 1 when at least one value is missing, and 2 for
invalid inputs or report-writing errors. Output paths cannot overwrite inputs or each other.

## Matching rules

| Status | Meaning |
| --- | --- |
| EXACT | The normalized value appears as a substring on a page. |
| FUZZY | Best positive similarity meets the **unrounded** threshold. |
| MISSING | No usable text, no positive similarity, or a score below threshold. |
| SKIPPED | Value is blank or becomes empty under the selected normalization options. |

Pages are searched in ascending numeric order; ties choose the earliest page. `reverse`
adds a reversed word-order candidate. Full-page fragments shorter than the expected
value use a length-sensitive ratio, avoiding a misleading 100% partial score.

Baseline normalization: Unicode NFKC, casefold, whitespace collapse. Optional flags:
`normalize_digits`, `strip_punctuation`, `fold_diacritics`, `reverse`. The pass rate is
`(exact + fuzzy) / (total - skipped)`, or zero if nothing is checked.

**Duplicate review:** repeated words such as `Areeb Areeb Khan` or `Areeb Khan Khan` are
flagged in the spreadsheet and PDF. Repeated full names on the same or different pages
include occurrence totals and per-page counts. Use the **Review duplicates** filter;
HTML/XLSX reports include these findings too. Repetition may be intentional: review flags
do not change status, match rate, or CLI exit codes. See [docs/DUPLICATES.md](docs/DUPLICATES.md).

**Scope:** matching verifies occurrence anywhere in the document. It does not verify
that values belong to the same person/row, require a particular number of appearances,
enforce whole-word boundaries for match status, or compare across page breaks. The additional
occurrence counts use full-value word boundaries. For example, a short code can occur inside a
longer code. Review short identifiers and fuzzy matches. Spreadsheet values are underlying
cell values, not Excel's displayed number formatting. Formula cells require saved cached
results (recalculate and save in Excel first); ProofCheck does not evaluate formulas.

## Performance changes

- Normalize document pages once per run and reuse repeated cell results.
- Stop exact-match work before any fuzzy scoring; align only the winning fuzzy snippet.
- Use native PDFium text extraction by default; set `PROOFCHECK_PDF_ENGINE=pdfplumber`
  when its layout extraction is better for a particular file.
- OCR a bounded batch of pages with two workers by default. Native PDFium calls are
  serialized under one process-wide lock; Tesseract runs in parallel on detached images.
- Skip OCR on uniform blank images; cap per-page OCR work and render size.
- Reuse content-addressed OCR within its retention window. Failed OCR is not cached.
- Keep synchronous processing outside the API event loop. Reject excess work with 429.
- Render at most 100 table rows and debounce search instead of rebuilding thousands of rows.

Measured synthetic improvements and reproducible commands are in [docs/PERFORMANCE.md](docs/PERFORMANCE.md).

## API and limits

The existing endpoints remain: `/api/health`, `/api/inspect`, `/api/check`, auth,
history, and `/reports/{run_id}.{ext}`. `/docs` exposes OpenAPI. The additive
`columns_json` form field supports headers containing commas or newlines; legacy `columns`
is still accepted. Responses add `timings` in seconds. See [docs/API.md](docs/API.md).

Default limits include 50 MiB per upload, two concurrent inspections/checks per server
process, 1,000 pages, 100,000 spreadsheet data rows, 200,000 selected cells, 10 million
extracted characters, and 40 million pixels per rendered page/image. OCR DPI is 72–600.
See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for all settings and tradeoffs.
For larger local PDFs, version 0.3.2 accepts `MAX_UPLOAD_MB` up to `10240` (10 GiB).
The configuration guide includes a Windows launch command and troubleshooting for the
old `between 1 and 5120` startup error. Raising admission limits does not guarantee
multi-gigabyte processing capacity; page/text limits and disk requirements still apply.

Duplicate nonblank headers are rejected, rather than silently checking the wrong column.
Empty/corrupt files and invalid options return readable errors. Multi-frame images are
explicitly rejected: export their frames as separate images or a PDF.

## Privacy and authentication

Local use defaults to authentication **off**: all users then share the anonymous workspace.
Enable authentication and HTTPS before exposing the service to other users. Set a strong,
stable `PROOFCHECK_SECRET`; do not reuse example passwords. Reports require the authenticated
owner when auth is enabled. An opaque report ID alone no longer grants access.

Uploads are temporary and removed after success or failure. Reports contain input values
and last about one hour. OCR cache entries contain extracted text, default to a one-day
TTL and a 512 MiB budget, and can be disabled. History stores filenames and counts until
deleted; filenames can themselves contain personal information. See deployment notes for
retention, persistent volumes, sessions, and resource isolation.

## Validate and review

```bash
python -m pytest -q
npm ci
npm run test:ui
npx playwright install chromium
npm run test:browser
python scripts/benchmarks/processing.py
```

Node is used only for frontend tests; the application itself needs no Node runtime or build.
The browser test starts its own temporary server and creates synthetic test files.

Read [docs/AUDIT.md](docs/AUDIT.md), [docs/TESTING.md](docs/TESTING.md), and
[CHANGELOG.md](CHANGELOG.md). The delivered ZIP includes the source, tests, documents,
benchmark evidence, and Git history. Unzip, then use `git log` inside the project directory
to review the baseline and descriptive implementation commits. Virtual environments,
installed dependencies, caches, and real user uploads are excluded.

The original proprietary terms in [LICENSE.md](LICENSE.md) remain in effect.
