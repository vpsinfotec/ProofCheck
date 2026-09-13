# Validation record — 0.3.1

Validation used generated fixtures, including the names supplied as edge-case examples.
No uploaded spreadsheets, scans, or production credentials are included in this repository.

## Baseline

The supplied archive's staged modifications were preserved as commit `9c9502c`. Running
its original suite produced **69 passes and 2 failures**: PDF extraction tests expected
`_resolve_engine`, but the provided implementation no longer contained it.

## Release checks

| Check | Result |
| --- | --- |
| Python regression suite | 150 passed, no failures. |
| Frontend DOM regression suite | 8 passed, no failures. |
| Live headless Chromium | Passed real upload/check with 350 exact values, same/cross-page duplicate counts, repeated words, review filter, comma-containing header, pagination, search, download, picker cancellation, route return, 390px mobile layout, and no page errors. |
| Python wheel | Built successfully; installed/imported outside the source tree; health and static assets verified; no documentation namespace or bytecode accidentally packaged. |
| Dependency compatibility | pip check passed. |
| JavaScript syntax | node --check passed. |
| Source whitespace validation | git diff --check passed. |
| Synthetic benchmarks | 5 workload comparisons, 3 repetitions each, expected/status/page/score parity. |

Environment: Linux x86_64, Python 3.12.14, Node 24.19.0. Runtime dependencies are specified
in pyproject.toml; frontend test dependencies are locked in package-lock.json. Browser
verification used Chromium 153 supplied as a local executable with Playwright 1.61.1.
The default Playwright browser download was unavailable in this environment; the same
committed test ran against the local Chromium executable through CHROMIUM_PATH.

New duplicate regressions cover the concrete Areeb examples, repeated middle words,
source repetitions, later-page findings, Unicode/normalization, boundaries, reverse
overlap, cache isolation, legacy history, and real API/HTML/XLSX propagation. The
duplicate-name benchmark checks all occurrence totals and repeated-word findings.

The Python suite emits two upstream deprecation warnings: Starlette's compatibility with
httpx and an AnyIO BlockingPortal alias. They are not application test failures. The npm
runner also reports the environment's proxy-setting notice; the app does not use npm at runtime.

## Reproduce

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,ocr]"
python -m pytest -q
npm ci
npm run test:ui
npx playwright install chromium
npm run test:browser
python scripts/benchmarks/processing.py
python -m pip wheel . --no-deps --wheel-dir dist
```

Install the Tesseract executable separately to exercise real OCR diagnostics. Optional
OCR tests that require a live engine are marked accordingly; this validation environment
had Tesseract installed. The UI test suite uses JSDOM and controlled network responses to
force request races; the browser test exercises a real temporary FastAPI server and real
spreadsheet/PDF uploads. It removes its generated fixture/database/report directory after use.

To use another installed browser/Python runtime:

```bash
CHROMIUM_PATH=/path/to/chromium PROOFCHECK_TEST_PYTHON=/path/to/python npm run test:browser
```

The benchmark requires the delivered Git history. It imports tracked baseline code into
separate namespaces and asserts verdict parity on representative fixtures; corrected edge
cases are covered separately. Timings are synthetic medians, not production guarantees.

## Not validated

No Docker daemon, hosted deployment, external Git push, Windows/macOS setup execution,
production scan corpus, multi-host infrastructure, or large-scale adversarial load test was
available/performed. Mobile Chromium was checked; Safari/Firefox were not exercised. A real
OCR-heavy workload remains the appropriate final capacity/accuracy check before deployment.
