# Deploy ProofCheck 0.3.2

ProofCheck needs a Python server and a writable filesystem. OCR additionally needs the
Tesseract executable and language packs. Static hosting alone cannot run its backend.
The default supported layout is one host/container with persistent local SQLite storage.

## Docker

```bash
docker compose up --build -d
docker compose logs -f
docker compose down
```

Compose binds to 127.0.0.1 by default; deliberately change the binding or use a reverse
proxy for shared access. The Dockerfile installs English Tesseract, runs as an unprivileged application user,
and checks `/api/health`. The named `/data` volume retains SQLite, OCR cache, and reports.
Build/run commands are provided for deployment; Docker execution was not available in
the validation environment. See [docs/TESTING.md](docs/TESTING.md) for verified gates.

For shared access, configure authentication, a generated secret, credentials, and TLS:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Place that output in your deployment's `PROOFCHECK_SECRET`. Set `PROOFCHECK_AUTH=on`,
`PROOFCHECK_ADMIN_USER`, and `PROOFCHECK_ADMIN_PASSWORD`; restart to bootstrap the first user.
Set `PROOFCHECK_COOKIE_SECURE=on` behind HTTPS. Keep self-registration off unless intended.
The provided Compose file defaults to local anonymous use; override its environment for
shared deployment. Do not expose the anonymous default to the internet.

## Direct Python service

```bash
python -m venv .venv
.venv/bin/python -m pip install ".[ocr]"
PROOFCHECK_DB=/var/lib/proofcheck/proofcheck.db \
PROOFCHECK_OCR_CACHE=/var/lib/proofcheck/ocr_cache \
PROOFCHECK_REPORT_DIR=/var/lib/proofcheck/reports \
.venv/bin/uvicorn proofcheck.web.app:app --host 127.0.0.1 --port 8000
```

Create the data directory owned by the service account. Install Tesseract using the
operating system package manager. Use a service manager and a TLS reverse proxy for
shared access. Trust forwarded scheme/IP headers only from your own proxy, and set
an explicit CORS allow-list if the frontend is hosted separately.

Configure request size and upstream timeouts at the proxy as well as application limits.
Keep the upstream response timeout long enough for your measured OCR workload. A 120-second
per-page OCR limit is not a 120-second whole-request limit. Very long OCR jobs need a
persistent worker queue or smaller documents; this release retains the synchronous API.

## Capacity planning

Start with one web worker, two admitted checks/inspections, and two OCR workers per check.
The API threadpool stays responsive while file processing runs. At most four Tesseract
processes may run at once under those settings, with `OMP_THREAD_LIMIT=1` unless overridden.
PDFium native operations are serialized within a process for safety. Increasing thread
counts does not parallelize PDFium. Large render buffers and OCR preprocessing can consume
several times an image's raw size; size memory limits accordingly.

Multiple local Uvicorn workers multiply both admission and rate limits. All workers must
share the same secret, SQLite path, and report path. Keep SQLite on supported local storage,
not an arbitrary network filesystem. Independent replicas need a shared database and report
storage design; the included configuration does not implement that distributed architecture.

## Data and retention

- Upload copies are deleted at the end of a request, including failures.
- HTML/XLSX reports contain input data and expire after one hour. Cleanup runs each minute
  during server lifespan and on relevant report requests.
- OCR cache text expires after one day and has a default 512 MiB cleanup budget.
- History persists filenames/counts/settings until deleted. Filenames may contain PII.
- Users persist salted password hashes; passwords are not stored in plaintext.
- Session cookies are signed, not encrypted. Logout clears the browser cookie; a copied
  token remains valid until expiry unless its user is removed or the signing key changes.

Restrict data directories and backups to authorized operators. Report IDs are opaque, but
report download authorization is enforced independently. Changing Tesseract/language data
requires changing `PROOFCHECK_OCR_CACHE_NAMESPACE` or clearing OCR cache to avoid stale OCR.

The ZIP omits installed dependencies and runtime data. Git history is included for review.
No deployment, external repository push, database migration, or real-user load test was
performed as part of the code audit.

## Platform examples

The existing `deploy/` manifests are example starting points for Fly, Render, Heroku,
Netlify, and Vercel. They were not deployed or validated against current provider limits.
Use the Dockerfile for the backend; Netlify/Vercel examples only serve/proxy the frontend.
Ensure `/api/*` and `/reports/*` reach the same authenticated backend. Provider-specific
filesystem and request timeouts can make long OCR requests unsuitable for those plans.

Full environment settings: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).
