# API reference for 0.3.2

The web UI and API use the same origin. Cookie authentication applies to inspection,
checks, history, and reports when enabled. All API/report responses are non-cacheable.
Version 0.3.2 accepts `MAX_UPLOAD_MB` from 1 to 10240 MiB, retaining the 50 MiB default.
Health returns the configured size in bytes; the bundled UI adopts it without a source edit.

| Endpoint | Behavior |
| --- | --- |
| GET /api/health | status, version, auth_enabled, ocr_available, max_upload_bytes, registration_enabled. |
| POST /api/inspect | Multipart excel plus optional header_row (default 1); returns sheets and headers. |
| POST /api/check | Multipart excel and pdf plus options; returns complete result and download URLs. The pdf field also accepts an image. |
| GET /reports/{run_id}.{ext} | Owned report download, ext html or xlsx, run ID 32 lowercase hex characters. |
| POST /api/auth/login | JSON username/password; sets HttpOnly, SameSite=Lax session cookie. |
| POST /api/auth/logout | Clears the browser session cookie. |
| POST /api/auth/register | Optional registration; trims username before storage and token creation. |
| GET /api/auth/me | Current user or 401. |
| GET /api/history | Latest 100 summaries owned by current user. |
| GET /api/history/{run_id} | Owned summary or 404. |
| DELETE /api/history/{run_id} | Delete owned summary and report files, or 404. |

## Check form fields

- `columns_json`: JSON array of exact header names, e.g. `["Last, First", "City"]`.
  Takes precedence when supplied. This is the preferred form for new clients.
- `columns`: legacy comma/newline-separated names.
- `all_columns`: false by default; ignores the selection when true.
- `sheet`: optional sheet name, default active sheet for direct API/CLI callers.
- `header_row`: default 1.
- `fuzzy_threshold`: default 90.
- `normalize_digits`, `strip_punctuation`, `fold_diacritics`, `reverse`: false.
- `ocr`: false for PDF fallback; images inherently need OCR.
- `ocr_lang`: eng; `ocr_dpi`: 300; `ocr_psm`: 6; `ocr_cache`: true.

Invalid booleans are rejected rather than silently treated as false.

```bash
curl -F excel=@delegates.xlsx -F pdf=@program.pdf \
  -F 'columns_json=["Name","City"]' http://127.0.0.1:8000/api/check
```

A successful response retains `meta`, `summary`, `columns`, `warnings`, and `report_urls`.
It adds `timings`: load_excel, extract_document, match, pipeline, reports, total, in seconds.
`total` covers server-side upload copying, processing, and report creation before JSON
serialization; it excludes network upload/download and browser rendering. Reports timing
also includes ownership/history persistence. Match timing includes document preparation.

Each row retains row, expected, status, page, best_match, score, diff, and source.
`diff` is a list of `[operation, text]` pairs. Status decisions use the unrounded score;
`score` is the integer display value. Clients must render strings as text or escape HTML.

## Duplicate review (additive in 0.3.1)

Each row adds:

| Field | Meaning |
| --- | --- |
| `occurrence_count` | Sum of full-value, non-overlapping occurrences across extracted pages. |
| `occurrences` | Sorted list of `{ "page": 1, "count": 2 }`, omitting zero-count pages. |
| `repeated_words` | List of `{ "word": "areeb", "count": 2, "page": 1 }`; `page: null` means the spreadsheet value. Count is the largest consecutive run for that word at that location. Words are normalized. |
| `needs_review` | True when occurrence count exceeds 1 or repeated-word findings exist. |

`summary.duplicate_review` counts flagged cells across selected columns. It is an integer
in every new check and is persisted in history. Older history records return `null` for
this field, meaning not recorded; clients should not interpret that as zero findings.

Statuses, scores, primary page, pass rate, and error codes retain their existing meaning.
An `EXACT` result can also have `needs_review: true`. Review duplicate evidence independently
of match status. These fields describe extracted text, not unique people. Counting uses
word boundaries and configured normalization; approximate duplicates and cross-page phrases
are not counted. See [DUPLICATES.md](DUPLICATES.md) for examples and limitations.

## Errors

| Status | Meaning |
| --- | --- |
| 400 | Unsupported/empty/corrupt upload or malformed request. |
| 401 | Authentication required/invalid credentials. |
| 403 | Registration disabled. |
| 404 | Missing, expired, deleted, or other user's report/history. |
| 413 | Per-file or aggregate upload limit exceeded. |
| 422 | Invalid options, columns, worksheet, document, or other pipeline input. |
| 429 | Processing capacity or authentication rate limit; respect Retry-After. |
| 500 | Generic internal failure; detailed diagnostic is logged on the server. |

Errors include a human-readable `error` string. HTTP errors also retain `detail` for old
clients. Do not automatically retry POST /api/check: a lost response may already have
created a run. There is no idempotency key, job polling, or durable cancellation protocol.
In-browser navigation preserves an in-flight request; a disconnected client does not
terminate the worker or Tesseract process. The per-page OCR timeout still applies.

## Migration differences

The 5 GiB implicit upload default is now 50 MiB; DPI above 600 is rejected. Duplicate
headers are rejected; duplicate requested names are checked once. Empty normalized values
are skipped; zero-similarity/empty documents never pass merely because threshold is zero.
Short page fragments are scored with a length-sensitive ratio. Fuzzy ties select the
lowest page consistently. Accurate Unicode snippet spans replace proportional offsets.
Auth-enabled report URLs now require the owner session. OCR caches use revision v2 and a
configurable namespace. PDFium is the default text extractor; pin pdfplumber to retain its
specific layout extraction if required.
