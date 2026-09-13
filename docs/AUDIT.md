# Frontend and backend audit — updated 2026-09-13

Scope: the supplied Proofcheck(1).zip, including its existing Git history and staged source.
No production service, production logs, real matching corpus, or deployment credentials
were supplied. This is a code audit and verified local remediation, not proof that every
possible defect or operational failure has been eliminated.

## Findings and remediation

| Area | Finding in supplied code | Implemented solution | Evidence |
| --- | --- | --- | --- |
| Matching | Every cell normalized every page. | PreparedMatcher normalizes once per run. | Matcher regressions; benchmark. |
| Matching | Exact hits still fuzzy-scored all pages. | Exact-first short circuit. | Fuzzy scorer forbidden in exact-hit test. |
| Matching | Repeated cells recomputed all work. | Run-local memoization with independent row/diff objects. | Duplicate mutation isolation test. |
| Matching | Repeated first/last name words could be hidden by an exact substring; middle-word duplication could break the phrase. | Separate repeated-word review index flags source and document repetitions without altering verdicts. | Areeb Areeb Khan, Areeb Khan Khan, and repeated-middle-word regressions. |
| Matching | First exact hit hid repeated appearances on the same/later pages. | Full-value occurrence totals and page counts, with boundary and reverse-overlap rules. | Same-page/cross-page, prefix, reverse, and later-page regressions. |
| Frontend/reports | No duplicate evidence or review filter. | Review badge, details, summary, filter, HTML/XLSX output, and persisted count; old history marked not recorded. | Real API/report integration, DOM test, and live Chromium. |
| Matching | Best snippet recalculated on every improving candidate. | Align only the winner. | Mixed benchmark and snippet tests. |
| Matching | Proportional raw offsets failed after Unicode/whitespace changes. | Original character span mapping. | Ligature/whitespace fixture and Unicode cases. |
| Matching | Fuzzy ties depended on dictionary insertion order. | Numeric page sorting with first-wins ties. | Unsorted-page tie tests. |
| Matching | Rounded scores incorrectly crossed threshold. | Compare unrounded score; retain integer display. | 89.6 vs 90 regression. |
| Matching | Empty normalized values/no-text input could falsely pass. | Skip normalized empties; missing for no positive match. | Threshold-zero tests. |
| Matching | Short page fragments received full partial-ratio scores. | Length-sensitive ratio for pages shorter than expected text. | Long name against one-word page test. |
| PDF | Native extraction implementation missing although tests required it. | PDFium default with pdfplumber override. | Baseline 2 failures; both engines now pass. |
| PDF/OCR | Unbounded native resources and unsafe potential concurrency. | Shared PDFium lock and explicit resource closure. | Engine tests and live OCR diagnostics. |
| OCR | Sequential page processing and unnecessary blank-page subprocesses. | Bounded page pool, detached images, blank shortcut. | OCR tests and blank engine-call guard. |
| OCR | No process deadline/render size limit. | Per-page timeout and pixel limits. | Oversized image test; timeout configuration. |
| OCR | A failed page discarded text recovered on other pages. | Keep successful pages through the failed batch, warn and stop subsequent batches. | Partial-failure and post-OCR size regressions. |
| Images | EXIF orientation ignored, multi-frame files silently truncated. | Apply orientation; explicitly reject multiple frames. | Multi-frame and size regressions. |
| Cache | Shared .tmp path raced under concurrent writes. | Unique private temporary files plus atomic replace. | 80 concurrent cache writes. |
| Cache | Corrupt JSON/types/page keys could crash a run. | Validate entries and treat corruption as a miss. | Malformed cache parametrization. |
| Cache | Image OCR failures cached as empty successes. | Cache only successful recognition. | Fail-then-recover regression. |
| Cache | Cached images required an installed engine. | Check cache before checking engine availability. | Engine removed after caching test. |
| Cache | Extracted text persisted indefinitely. | TTL, disk budget, explicit upgrade namespace. | Budget and namespace tests. |
| Workbook | Duplicate headers silently selected the wrong column. | Reject ambiguous headers; deduplicate requested names. | Workbook regression fixtures. |
| Workbook | Unbounded expanded ZIP size/dimensions/selected cells. | Expanded-byte, row, column, selected-cell limits. | Limit regression fixtures. |
| Workbook | Empty header/data runs could appear successful. | Reject empty selections and no-data sheets. | Pipeline/CLI validation. |
| API | CPU/filesystem work blocked async event loop. | Synchronous threadpool routes. | Health response while check is blocked. |
| API | Size checked only after multipart had spooled upload. | Content-Length and streamed aggregate limits before parsing, per-file validation retained. | Declared and chunked 413 tests. |
| API | Unbounded simultaneous expensive checks. | Process-local admission and Retry-After. | Busy request rejected without reading body. |
| API | Second-upload failures could risk partial file retention. | Cleanup on every path, including empty/oversize uploads. | Tempfile cleanup regressions. |
| API | Comma/newline headers could not be selected reliably. | Add columns_json; retain legacy columns. | Real comma-header API and browser checks. |
| API | Arbitrary DPI/threshold/PSM/language/boolean inputs. | Typed validation and shared pipeline validation. | Invalid option parametrization. |
| API | Exception strings exposed internal paths. | Generic 500 message with server-side logging. | Deliberate secret-like exception fixture. |
| Reports | URLs bypassed authentication and ownership. | Require user and owned run record. | Owner/anonymous/other-user access tests. |
| Reports | Formula-looking strings executed as Excel formulas. | Explicit string cell types. | Reopen generated XLSX and inspect cell types. |
| Reports | Invalid/duplicate/truncated sheet names could crash exports. | Sanitize and allocate unique 31-character titles. | Report name edge cases. |
| Auth | Malformed Unicode/oversized tokens could raise errors. | Bound/catch parsing, precise expiry, require existing user. | Token regressions. |
| Auth | Registration trimmed storage name but signed untrimmed identity. | Normalize once before both operations. | Registration followed by /me test. |
| Auth | No secure-cookie option or request/login bounds. | HTTPS/forced Secure cookies, credentials/body limits, bounded IP rate tracking. | Auth tests and middleware review. |
| Storage | SQLite context managers committed but did not close connections. | Explicit transaction context and finally close; WAL initialized once per schema setup. | Full API/history suite. |
| Frontend | Run enabled before inspection/selection was ready. | Explicit inspected/running state and readiness hints. | UI state regression. |
| Frontend | Stale inspect replies replaced newer selections. | AbortController plus sequence and view checks. | Out-of-order response test. |
| Frontend | Input changes could enable duplicate runs. | Lock controls and guard a global running flag. | Double-click test. |
| Frontend | Picker opening cleared the prior selection even on cancel. | Preserve files on picker cancellation. | Chromium cancel event check. |
| Frontend | Late history/login/check callbacks targeted destroyed views. | View tokens/scoped callbacks and run state restoration. | UI navigation test and live route return. |
| Frontend | Every result rendered, and search rebuilt all rows per keystroke. | 100-row pagination, precomputed search strings, debounce. | 20,050-row DOM regression. |
| Frontend | API arrays/network failures produced poor error messages. | Central request/error handling and readable status banners. | Validation-array and failed-inspection tests. |
| Frontend | Overflow and focus feedback on small screens. | Scrollable tables, focus outlines, status announcements, reduced motion. | 390px Chromium width assertion. |
| CLI | inspect ignored header-row/sheet and marked every sheet active. | Honor both options without misleading active markers. | CLI regression. |
| CLI | Huge page ranges materialized before bounds filtering. | Clamp before range expansion. | Trillion-page range test. |
| CLI | Output paths could overwrite input workbooks/documents. | Reject overlapping input/output paths. | CLI regression. |
| Build/docs | Package discovery could include documentation as a namespace. | Restrict to proofcheck and proofcheck.*; version 0.3.0. | Wheel contents validation. |
| Docs | Defaults, architecture, privacy and no-ML OCR claims were inconsistent. | Update README, deployment, configuration/API/audit/testing docs and module notes. | Current source/doc review. |

## Remaining boundaries and risks

- No production workload was supplied. The performance table is synthetic; OCR-heavy
  performance and accuracy need a representative corpus.
- Whole-request hard cancellation and restart-safe progress need a durable job service.
  Disconnecting a browser does not kill server work; hard public-service isolation is an
  OS/container responsibility. Complex native documents can exceed ordinary assumptions.
- Matching remains document-wide substring/fuzzy occurrence, not record association,
  whole-token identity validation, or cross-page phrase matching. Duplicate review counts
  full-value occurrences and adjacent repeated words; it does not infer expected multiplicity
  or unique people, enumerate approximate duplicates, or resolve extraction/layout ambiguity.
  See [DUPLICATES.md](DUPLICATES.md).
- Excel formulas are not recalculated and display formatting is not reproduced. Missing
  cached formula values are read as blanks; recalculate and save the source workbook.
- Multi-frame images are rejected with a warning rather than silently checking only frame 1.
- A page OCR failure retains successful text recovered through its batch and warns about
  the failure; later batches stop. Full per-page retry/result persistence is future work.
- API result JSON remains complete and may be large despite browser pagination. Reports
  are generated synchronously and can dominate large exports.
- Session logout clears a cookie but does not revoke a stolen copy of a stateless token.
  In-process IP rate limiting is not a distributed anti-abuse service.
- Multi-host deployment, real proxy behavior, Windows/macOS installers, Docker builds,
  and production load tests were not exercised here.

Tesseract's recognition model is learned, despite earlier documentation claiming otherwise;
see the [official Tesseract manual](https://tesseract-ocr.github.io/tessdoc/). Its use remains
local and independent of cloud LLM services. PDFium's required threading restriction is
confirmed in its [official API documentation](https://pypdfium2.readthedocs.io/en/stable/python_api.html#incompatibility-with-threading).
