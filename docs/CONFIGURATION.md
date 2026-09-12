# Configuration reference

Resource settings are read when modules are imported. Restart after changing them.
Invalid resource settings fail with an explanatory configuration error.

| Variable | Default | Purpose |
| --- | --- | --- |
| MAX_UPLOAD_MB | 50 | MiB per file; valid configuration range 1–5120. |
| PROOFCHECK_MAX_CONCURRENT_CHECKS | 2 | Checks plus inspections admitted per process, 1–8; extra requests get 429 and Retry-After. |
| PROOFCHECK_PDF_ENGINE | auto | auto chooses pdfium; pdfplumber remains available. Different extraction layouts can change results. |
| PROOFCHECK_MAX_PAGES | 1000 | Maximum PDF pages or image files in a folder. |
| PROOFCHECK_MAX_ROWS | 100000 | Maximum spreadsheet data rows below the header. |
| PROOFCHECK_MAX_CELLS | 200000 | Maximum selected row-column values. |
| PROOFCHECK_MAX_TEXT_CHARS | 10000000 | Extracted text limit. |
| PROOFCHECK_MAX_IMAGE_PIXELS | 40000000 | Maximum image or rendered page size. |
| PROOFCHECK_MAX_WORKBOOK_MB | 256 | Maximum declared expanded XLSX ZIP size. |
| PROOFCHECK_OCR_WORKERS | 2 | Concurrent Tesseract page workers, 1–4. |
| PROOFCHECK_OCR_PAGE_SECONDS | 120 | Total OCR-strategy budget per page; each subprocess receives the remaining timeout. |
| OMP_THREAD_LIMIT | 1 if unset | Tesseract native thread limit; avoids multiplying native and page-worker threads. |
| PROOFCHECK_OCR_CACHE | temporary proofcheck/ocr_cache directory | Cache directory; off/false/0/no disables it. |
| PROOFCHECK_OCR_CACHE_TTL_SECONDS | 86400 | Age after which OCR entries expire. |
| PROOFCHECK_OCR_CACHE_MAX_MB | 512 | Approximate disk budget, enforced by scheduled cleanup while the web server runs. |
| PROOFCHECK_OCR_CACHE_NAMESPACE | default | Change after engine or language-pack upgrades to invalidate prior OCR output. |
| PROOFCHECK_REPORT_DIR | temporary proofcheck_reports directory | Generated reports; set a shared writable path for multiple local workers. |
| PROOFCHECK_DB | temporary proofcheck/proofcheck.db | SQLite users and history path. |
| PROOFCHECK_AUTH | off | on enables cookie authentication. Off means all visitors share one identity. |
| PROOFCHECK_SECRET | random per-process fallback | Strong stable secret required operationally across restarts/workers. Empty values use the random fallback, never an empty signing key. |
| PROOFCHECK_SESSION_HOURS | 12 | Clamped to 1 minute through 7 days. |
| PROOFCHECK_COOKIE_SECURE | off | on forces Secure cookies; HTTPS requests also set Secure. |
| PROOFCHECK_ADMIN_USER / PROOFCHECK_ADMIN_PASSWORD | unset | Bootstrap the first user at startup when auth is enabled. |
| PROOFCHECK_ALLOW_REGISTER | off | on enables the registration API when auth is on. |
| CORS_ORIGINS | local HTTP origins | Comma-separated explicit trusted origins. Avoid wildcard origins with cookies. |
| TESSERACT_CMD | auto-detected | Optional full path to the engine binary. |

Report TTL is one hour. Web lifespan cleanup runs every 60 seconds and on relevant
report requests. OCR reads also reject expired entries; cache disk-budget cleanup occurs
in the web process. For CLI-only operation, schedule `ocr_cache.cleanup()` or disable caching.
New cache/report directories are created with mode 0700; existing directories keep their
existing permissions. Restrict them to the application account. Cache temporary files use
unique names and mode 0600, followed by atomic replacement.

Per-run OCR PSM choices: 3, 4, 6, 7, 8, 11, 12, 13. Default is 6. Language syntax is a
pack name or plus-separated pack names (for example eng+ara); packs must be installed.
Header row range is 1–1048576; fuzzy threshold is 0–100; OCR DPI range is 72–600.
Workbook header inspection rejects more than 4096 declared columns. Remove stray formatting
that inflates spreadsheet dimensions before raising resource limits.

The aggregate request-body limit for inspection/checking is twice the per-file limit plus
1 MiB for multipart fields. Both Content-Length and actual streamed bytes are checked.
Individual uploads are still checked independently. Login/registration bodies are capped
at 16 KiB; their rate is limited to 20 requests/minute per client IP per process.

These limits bound ordinary workloads. They do not provide OS-level CPU/memory isolation
for hostile documents or a hard whole-request deadline. Use a container/process boundary
and gateway limits when accepting untrusted public uploads.
