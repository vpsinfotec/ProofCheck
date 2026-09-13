# Architecture and design decisions

## Boundaries

| Layer | Ownership |
| --- | --- |
| CLI / FastAPI routes | Validate boundary input, invoke the shared pipeline, write/serialize reports. |
| Web resource middleware | Admission, streamed request limits, authentication entry check, private response headers, login rate bounds. |
| Pipeline | Validate run configuration, load values, extract document text, prepare matcher, aggregate results and timings. |
| Excel / document / PDF / images | Input decoding only; no UI or matching semantics. |
| PreparedMatcher / normalization | Deterministic comparisons, normalized page reuse, duplicate result reuse, source span mapping. |
| DuplicateAuditor | Full-value occurrence counts and repeated-word review on shared normalized text; no verdict rewriting. |
| OCR / cache | Recognition strategies, safe rendering, bounded native/subprocess work, atomic content-addressed retention. |
| Models / web schemas | Internal dataclasses and stable, additive JSON boundary. |
| Report writers / humanize | Presentation from RunResult only; HTML escaping and inert Excel string cells. |
| Store / auth | Short-lived SQLite connections, owned history, password hashes, signed cookies. |
| Static UI | Request lifecycle and presentation; no duplicated matcher or OCR logic. |

## Request lifetime

A processing request is admitted before multipart parsing. Missing auth, oversized bodies,
and excess capacity are rejected early. FastAPI executes synchronous processing routes in
its worker threadpool; the event loop remains available. Validated uploads are copied to
unique temporary paths. A try/finally removes copies on success and failure, including
failure while copying the second upload. Report ownership is persisted before result URLs
are returned. If report generation or ownership persistence fails, partially written reports
are removed and the request fails with a generic server error where appropriate.

The design follows FastAPI/Starlette's synchronous-route threadpool behavior; see the
[FastAPI concurrency guide](https://fastapi.tiangolo.com/async/#path-operation-functions).
Admission is process-local and includes uploads/inspection as well as matching; a stalled
uploader can occupy a slot. Use upstream request/connection timeouts for public access.

## Concurrency and memory

There is one PDFium lock shared between extraction and OCR rendering. Native pages,
text pages, bitmaps, and documents close explicitly under that lock. Detached PIL images
are then passed to a small OCR threadpool. Only one batch is retained; failure waits for
active OCR workers before closing their images. Tesseract gets a per-page time budget and
an OpenMP limit to reduce oversubscription. No process/thread result order affects matching
tie-breaking. SQLite uses WAL and every connection closes explicitly after its transaction.

## Matching and display

Pages are normalized once. An exact scan precedes fuzzy scoring and selects the first
matching page. Duplicate review separately scans all normalized pages and uses a prepared
repeated-word index, so later occurrences are retained without invoking fuzzy scoring for
exact hits. Repeated expected strings reuse both match and review computation, but rows
receive independent result instances, diff lists, and review lists. Fuzzy scanning keeps the highest score, with earliest-page
ties. Only its winning alignment is mapped to raw source spans. Combining sequences,
compatibility forms, casefold expansion, and whitespace are handled in the span mapping.

The frontend scopes callbacks to a view and uses monotonically increasing inspection
sequence IDs. Aborting an older request alone is not enough: a late reply is also ignored.
Run state is global to prevent duplicate checks and to survive route navigation. It is
not persisted across page reloads. Rendering flattens rows once, precomputes search text,
and inserts at most 100 rows; search input is debounced. Untrusted text is escaped.
Duplicate findings and their count come from the backend; the UI only renders and filters
them. Similarity status remains visible alongside the duplicate review badge. Old history
has a nullable review count to distinguish unaudited runs from runs with zero findings.

## Persistence

Reports and OCR caches contain document data. History contains filenames and summary
metadata and is not inherently free of PII. Authentication off intentionally shares one
anonymous workspace. Authentication on checks report/history ownership in SQLite. Cache
text is shared across runs with identical content and settings, but has no public retrieval
endpoint. Report deletion removes the owner record, so a stale file cannot subsequently
be downloaded through the API. See configuration and deployment notes for TTLs and limits.

The cache key includes revision, namespace, SHA-256 bytes, DPI, language, and PSM. Change
the namespace when engine/language data changes. Cache writes use private unique temporary
files and atomic replacement. Corrupt entries are cache misses, and OCR failures are never
persisted as successful empty image results.
