"""FastAPI application: routes + RunResult->JSON serialization only.

No matching/normalization logic lives here — every request is adapted into a
:class:`RunConfig`, handed to :func:`proofcheck.pipeline.run`, and the result is
serialized to the :mod:`schemas` contract. Uploads are real PII (delegate names) so
they are written to per-request tempfiles and deleted immediately after the run.
"""

from __future__ import annotations

import os
import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager, suppress
from threading import BoundedSemaphore

from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from ..limits import env_int

import tempfile
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__, ocr, ocr_cache, report_html, report_xlsx
from ..models import RunConfig, RunResult
from ..pipeline import PipelineError, run as pipeline_run
from . import auth, schemas, store
from .middleware import ResourceLimitsMiddleware

# ---- Configuration (env-driven, MVP-appropriate defaults) -------------------
MAX_UPLOAD_MB = env_int("MAX_UPLOAD_MB", 50, 1, 5120)
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost,http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    if o.strip()
]
REPORT_TTL_SECONDS = 60 * 60  # delete generated reports older than 1 hour

EXCEL_EXTS = {".xlsx", ".xlsm"}
PDF_EXTS = {".pdf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"}
DOC_EXTS = PDF_EXTS | IMAGE_EXTS  # /api/check accepts a PDF or a single image

_STATIC_DIR = Path(__file__).parent / "static"
# Short-lived cache for generated report files, keyed by run_id (download links).
# NOTE: production should move this to object storage with lifecycle expiry.
_REPORT_DIR = Path(os.environ.get("PROOFCHECK_REPORT_DIR", str(Path(tempfile.gettempdir()) / "proofcheck_reports")))
_REPORT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    store.init_db()
    auth.bootstrap_admin()
    async def cleanup_loop():
        while True:
            await asyncio.to_thread(_cleanup_reports)
            await asyncio.to_thread(ocr_cache.cleanup)
            await asyncio.sleep(60)
    cleanup = asyncio.create_task(cleanup_loop())
    try:
        yield
    finally:
        cleanup.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup


app = FastAPI(
    title="ProofCheck API",
    lifespan=lifespan,
    version=__version__,
    description="Local Excel-vs-document proof-reading with optional Tesseract OCR. "
    "The JSON contract here is the stable, swappable boundary; the bundled HTML "
    "UI is just one disposable client.",
)

app.add_middleware(ResourceLimitsMiddleware, upload_limit=lambda: MAX_UPLOAD_BYTES,
                   max_checks=env_int("PROOFCHECK_MAX_CONCURRENT_CHECKS", 2, 1, 8))

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,  # session cookie is sent on same-origin /api/* calls
)

# Serve the SPA's static assets (app.css / app.js). "/" still returns index.html below.
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ---- Error handling: human-readable JSON, never raw tracebacks --------------
@app.exception_handler(PipelineError)
async def _pipeline_error_handler(_: Request, exc: PipelineError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": str(exc)})


@app.exception_handler(Exception)
async def _unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.error("Unexpected request failure", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": "The check could not be completed. Please retry or contact the administrator."}, headers={"Cache-Control": "no-store"})


@app.exception_handler(StarletteHTTPException)
async def _http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail), "detail": exc.detail}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [f"{'.'.join(map(str, error['loc'][1:]))}: {error['msg']}" for error in exc.errors()]
    return JSONResponse(status_code=422, content={"error": "; ".join(errors)})


# ---- Helpers ----------------------------------------------------------------
def _cleanup_reports() -> None:
    """Delete report files older than the TTL. Called opportunistically per request."""
    cutoff = time.time() - REPORT_TTL_SECONDS
    for path in _REPORT_DIR.glob("*"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass


def _validate_ext(filename: str, allowed: set[str], kind: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"{kind} must be one of {', '.join(sorted(allowed))} (got {ext or 'no extension'}).",
        )
    return ext


def _save_upload(upload: UploadFile, suffix: str) -> str:
    """Stream an upload to a tempfile, enforcing the size cap; return its path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    total = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := upload.file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Limit is {MAX_UPLOAD_MB} MB.",
                    )
                out.write(chunk)
            if not total:
                raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    except BaseException:
        _safe_unlink(path)
        raise
    return path


def _safe_unlink(path: str | None) -> None:
    if path:
        try:
            os.unlink(path)
        except OSError:
            pass


def _serialize(result: RunResult, run_id: str) -> dict:
    """Map an internal RunResult onto the JSON swap contract."""
    payload = schemas.CheckResponse(
        meta=schemas.MetaModel(
            excel=result.meta.excel,
            pdf=result.meta.pdf,
            timestamp=result.meta.timestamp,
            fuzzy_threshold=result.meta.fuzzy_threshold,
            flags=result.meta.flags,
        ),
        summary=schemas.SummaryModel(
            total=result.summary.total,
            exact=result.summary.exact,
            fuzzy=result.summary.fuzzy,
            missing=result.summary.missing,
            skipped=result.summary.skipped,
            pass_rate=result.summary.pass_rate,
        ),
        columns=[
            schemas.ColumnResultModel(
                name=col.name,
                results=[
                    schemas.MatchResultModel(
                        row=r.row,
                        expected=r.expected,
                        status=r.status.value,
                        page=r.page,
                        best_match=r.best_match,
                        score=r.score,
                        diff=[(op, text) for op, text in r.diff],
                        source=r.source,
                    )
                    for r in col.results
                ],
            )
            for col in result.columns
        ],
        warnings=result.warnings,
        timings={k: round(v, 6) for k, v in result.timings.items()},
        report_urls=schemas.ReportUrls(
            html=f"/reports/{run_id}.html",
            xlsx=f"/reports/{run_id}.xlsx",
        ),
    )
    return payload.model_dump()


def _parse_bool(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"} if value is not None else False


def _summary_dict(result: RunResult) -> dict:
    s = result.summary
    return {
        "total": s.total, "exact": s.exact, "fuzzy": s.fuzzy,
        "missing": s.missing, "skipped": s.skipped, "pass_rate": s.pass_rate,
    }


def _meta_dict(result: RunResult) -> dict:
    m = result.meta
    return {
        "excel": m.excel, "pdf": m.pdf, "timestamp": m.timestamp,
        "fuzzy_threshold": m.fuzzy_threshold, "flags": m.flags,
    }


def _record_history(run_id: str, user: str, result: RunResult) -> None:
    """Persist metadata and report ownership; fail closed if storage is unavailable."""
    try:
        store.add_run(
            run_id=run_id,
            username=user,
            created_at=result.meta.timestamp,
            excel=result.meta.excel,
            pdf=result.meta.pdf,
            summary=_summary_dict(result),
            meta=_meta_dict(result),
        )
    except Exception:
        logger.exception("Could not persist report ownership")
        raise


def _history_item(record: store.RunRecord) -> schemas.HistoryItem:
    return schemas.HistoryItem(
        run_id=record.run_id,
        created_at=record.created_at,
        excel=record.excel,
        pdf=record.pdf,
        summary=schemas.SummaryModel(**record.summary),
        meta=schemas.MetaModel(**record.meta),
    )


# ---- Routes -----------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Serve the bundled disposable UI."""
    index_file = _STATIC_DIR / "index.html"
    return HTMLResponse(index_file.read_text(encoding="utf-8"))


@app.get("/api/health", response_model=schemas.HealthResponse)
def health() -> schemas.HealthResponse:
    return schemas.HealthResponse(
        status="ok",
        version=__version__,
        auth_enabled=auth.auth_enabled(),
        ocr_available=ocr.available(),
        max_upload_bytes=MAX_UPLOAD_BYTES,
        registration_enabled=auth.auth_enabled() and auth.registration_enabled(),
    )


@app.post("/api/inspect", response_model=schemas.InspectResponse)
def inspect(
    header_row: int = Form(1, ge=1, le=1_048_576),
    excel: UploadFile = File(...),  # noqa: A002
    user: str = Depends(auth.current_user),
) -> schemas.InspectResponse:
    """Return sheets + headers so the UI can build a column picker."""
    _validate_ext(excel.filename, EXCEL_EXTS, "Excel file")
    path = _save_upload(excel, suffix=".xlsx")
    try:
        from .. import excel as excel_mod
        headers = excel_mod.inspect(path, header_row=header_row)
        return schemas.InspectResponse(sheets=list(headers.keys()), headers=headers)
    except Exception as exc:  # ExcelError and friends -> clean 400
        raise HTTPException(status_code=400, detail=f"Could not inspect Excel file: {exc}")
    finally:
        _safe_unlink(path)  # PII: delete immediately


@app.post("/api/check")
def check(
    excel: UploadFile = File(...),  # noqa: A002
    pdf: UploadFile = File(...),
    columns: str = Form(""),
    columns_json: str = Form(""),
    all_columns: bool = Form(False),
    sheet: str = Form(""),
    header_row: int = Form(1, ge=1, le=1_048_576),
    fuzzy_threshold: int = Form(90, ge=0, le=100),
    normalize_digits: bool = Form(False),
    strip_punctuation: bool = Form(False),
    fold_diacritics: bool = Form(False),
    reverse: bool = Form(False),
    ocr: bool = Form(False),  # noqa: A002 - shadows the ocr module locally; resolved below
    ocr_lang: str = Form("eng", max_length=128, pattern=r"^[A-Za-z0-9_]+(?:[+][A-Za-z0-9_]+)*$"),
    ocr_dpi: int = Form(300, ge=72, le=600),
    ocr_psm: int = Form(6, ge=3, le=13),
    ocr_cache: bool = Form(True),
    user: str = Depends(auth.current_user),
) -> JSONResponse:
    """Run a full check and return the documented JSON shape + report download URLs."""
    started = time.perf_counter()
    _cleanup_reports()
    _validate_ext(excel.filename, EXCEL_EXTS, "Excel file")
    pdf_ext = _validate_ext(pdf.filename, DOC_EXTS, "PDF or image file")

    excel_path = _save_upload(excel, suffix=".xlsx")
    pdf_path = None
    try:
        # Save with the real extension so the pipeline routes PDFs vs images correctly.
        pdf_path = _save_upload(pdf, suffix=pdf_ext)

        # Columns arrive as a comma- (or newline-) separated form field.
        if columns_json:
            try:
                col_list = json.loads(columns_json)
                if not isinstance(col_list, list) or any(not isinstance(c, str) or not c for c in col_list):
                    raise ValueError()
            except (ValueError, TypeError) as exc:
                raise HTTPException(422, "columns_json must be a JSON array of non-empty header names.") from exc
        else:
            col_list = [c.strip() for c in columns.replace("\n", ",").split(",") if c.strip()]
        config = RunConfig(
            excel_path=excel_path,
            pdf_path=pdf_path,
            columns=col_list,
            all_columns=all_columns,
            sheet=sheet or None,
            header_row=header_row,
            fuzzy_threshold=fuzzy_threshold,
            normalize_digits=normalize_digits,
            strip_punctuation=strip_punctuation,
            fold_diacritics=fold_diacritics,
            reverse=reverse,
            ocr=ocr,
            ocr_lang=ocr_lang or "eng",
            ocr_dpi=ocr_dpi,
            ocr_psm=ocr_psm,
            ocr_cache=ocr_cache,
        )
        result = pipeline_run(config)

        run_id = uuid.uuid4().hex
        # Original filenames are kept only in meta; the cached files use the opaque run_id.
        result.meta.excel = Path((excel.filename or result.meta.excel).replace("\\", "/")).name
        result.meta.pdf = Path((pdf.filename or result.meta.pdf).replace("\\", "/")).name
        report_start = time.perf_counter()
        report_html.write(result, str(_REPORT_DIR / f"{run_id}.html"))
        report_xlsx.write(result, str(_REPORT_DIR / f"{run_id}.xlsx"))

        # Persist run metadata and ownership so it survives the short-lived report cache.
        _record_history(run_id, user, result)

        result.timings["reports"] = time.perf_counter() - report_start
        result.timings["total"] = time.perf_counter() - started
        return JSONResponse(content=_serialize(result, run_id), headers={"Cache-Control": "no-store"})
    except BaseException:
        if "run_id" in locals():
            for ext in ("html", "xlsx"):
                _safe_unlink(str(_REPORT_DIR / f"{run_id}.{ext}"))
        raise
    finally:
        # PII: delete uploads immediately, whether the run succeeded or failed.
        _safe_unlink(excel_path)
        _safe_unlink(pdf_path)


@app.get("/reports/{run_id}.{ext}")
def download_report(run_id: str, ext: str, user: str = Depends(auth.current_user)) -> FileResponse:
    """Download a generated report. run_id is validated to be a bare hex token."""
    _cleanup_reports()
    if ext not in {"html", "xlsx"} or not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise HTTPException(status_code=404, detail="Report not found.")
    if store.get_run(run_id, user) is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    path = _REPORT_DIR / f"{run_id}.{ext}"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report expired or not found.")
    media = "text/html" if ext == "html" else (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return FileResponse(path, media_type=media, filename=f"proofcheck-{run_id}.{ext}", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


# ---- Auth routes (optional; no-ops semantically when auth is disabled) -------
def _set_session_cookie(response: Response, token: str, request: Request) -> None:
    response.set_cookie(
        key=auth.SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=auth._truthy(os.environ.get("PROOFCHECK_COOKIE_SECURE")) or request.url.scheme == "https",
        samesite="lax",
        max_age=auth._session_seconds(),
        path="/",
    )


@app.post("/api/auth/login", response_model=schemas.AuthUser)
def login(credentials: schemas.Credentials, response: Response, request: Request) -> schemas.AuthUser:
    """Validate credentials and set an HttpOnly session cookie."""
    if not auth.auth_enabled():
        # Auth is off: there is nothing to log into; report the single-user identity.
        return schemas.AuthUser(username=auth.ANONYMOUS, authenticated=False)
    credentials.username = credentials.username.strip()
    if not auth.authenticate(credentials.username, credentials.password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    _set_session_cookie(response, auth.make_token(credentials.username), request)
    return schemas.AuthUser(username=credentials.username, authenticated=True)


@app.post("/api/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=schemas.AuthUser)
def me(user: str = Depends(auth.current_user)) -> schemas.AuthUser:
    """Return the current user (the dependency enforces 401 when auth is on)."""
    return schemas.AuthUser(username=user, authenticated=auth.auth_enabled())


@app.post("/api/auth/register", response_model=schemas.AuthUser, status_code=201)
def register(credentials: schemas.Credentials, response: Response, request: Request) -> schemas.AuthUser:
    """Self-service registration. Disabled unless PROOFCHECK_ALLOW_REGISTER is on."""
    if not auth.auth_enabled() or not auth.registration_enabled():
        raise HTTPException(status_code=403, detail="Registration is disabled.")
    credentials.username = credentials.username.strip()
    try:
        auth.register_user(credentials.username, credentials.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _set_session_cookie(response, auth.make_token(credentials.username), request)
    return schemas.AuthUser(username=credentials.username, authenticated=True)


# ---- Run history routes (persisted metadata; PII inputs are never stored) ----
@app.get("/api/history", response_model=schemas.HistoryList)
def history(user: str = Depends(auth.current_user)) -> schemas.HistoryList:
    return schemas.HistoryList(runs=[_history_item(r) for r in store.list_runs(user)])


@app.get("/api/history/{run_id}", response_model=schemas.HistoryItem)
def history_item(run_id: str, user: str = Depends(auth.current_user)) -> schemas.HistoryItem:
    if not run_id.isalnum():
        raise HTTPException(status_code=404, detail="Run not found.")
    record = store.get_run(run_id, user)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _history_item(record)


@app.delete("/api/history/{run_id}")
def delete_history_item(run_id: str, user: str = Depends(auth.current_user)) -> dict:
    if not run_id.isalnum() or not store.delete_run(run_id, user):
        raise HTTPException(status_code=404, detail="Run not found.")
    # Best-effort: also drop any cached report files for this run.
    for ext in ("html", "xlsx"):
        try:
            (_REPORT_DIR / f"{run_id}.{ext}").unlink()
        except OSError:
            pass
    return {"status": "deleted", "run_id": run_id}
