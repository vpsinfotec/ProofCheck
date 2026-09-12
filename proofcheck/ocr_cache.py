"""Content-addressed cache for OCR results — never OCR the same file twice.

OCR (render + Tesseract) is the slowest part of a run. Because it is deterministic — the
same PDF bytes at the same DPI/language always yield the same text — the result can be
safely cached keyed by a **SHA-256 of the file's content**.

That content hash is also the *change detector* the feature needs: re-uploading the **same**
file produces the same hash → cache hit → no OCR (the engine isn't even needed). A file
whose data changed produces a **different** hash → cache miss → it is OCR'd fresh. So
"detect whether the upload changed" falls out of content-addressing for free.

Entries are small JSON files under ``$PROOFCHECK_OCR_CACHE`` (default
``<tempdir>/proofcheck/ocr_cache``). Set ``PROOFCHECK_OCR_CACHE=off`` (or ``0``/``false``)
to disable caching entirely. The cache is best-effort: any I/O error degrades to "no cache".
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time

from .limits import env_int

CACHE_REVISION = "v2"
_CACHE_TTL = env_int("PROOFCHECK_OCR_CACHE_TTL_SECONDS", 86400)
from pathlib import Path

_DISABLED_VALUES = {"", "0", "off", "false", "no"}


def cache_dir() -> Path | None:
    """Resolve the cache directory, or ``None`` when caching is disabled."""
    val = os.environ.get("PROOFCHECK_OCR_CACHE")
    if val is not None:
        if val.strip().lower() in _DISABLED_VALUES:
            return None
        return Path(val)
    return Path(tempfile.gettempdir()) / "proofcheck" / "ocr_cache"


def enabled() -> bool:
    return cache_dir() is not None


def file_sha256(path: str, *, chunk: int = 1 << 20) -> str:
    """Stream a SHA-256 of the file's bytes (the content fingerprint / change key)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _entry_path(directory: Path, digest: str, dpi: int, lang: str, psm: int) -> Path:
    # DPI, language, and page-segmentation mode all change OCR output, so all are in the key.
    safe_lang = "".join(c for c in lang if c.isalnum() or c in "+-_") or "eng"
    return directory / f"{CACHE_REVISION}.{digest}.{dpi}.{safe_lang}.psm{int(psm)}.json"


def load(digest: str, *, dpi: int, lang: str, psm: int = 3) -> dict[int, str] | None:
    """Return cached ``{page: text}`` for this content+dpi+lang+psm, or ``None`` on miss."""
    directory = cache_dir()
    if directory is None:
        return None
    try:
        path = _entry_path(directory, digest, dpi, lang, psm)
        if time.time() - path.stat().st_mtime > _CACHE_TTL:
            path.unlink(missing_ok=True)
            return None
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        if any(not isinstance(v, str) or int(k) < 1 for k, v in raw.items()):
            return None
        return {int(k): v for k, v in raw.items()}
    except (ValueError, TypeError):
        return None


def store(digest: str, *, dpi: int, lang: str, pages: dict[int, str], psm: int = 3) -> None:
    """Persist ``{page: text}`` for this content+dpi+lang+psm. Best-effort (never raises)."""
    directory = cache_dir()
    if directory is None:
        return
    tmp = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path = _entry_path(directory, digest, dpi, lang, psm)
        fd, tmp = tempfile.mkstemp(prefix=".ocr-", suffix=".tmp", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({str(k): v for k, v in pages.items()}, fh)
        os.replace(tmp, path)  # atomic publish so readers never see a half-written file
    except OSError:
        pass
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def cleanup() -> None:
    """Expire cached text, including older cache revisions and interrupted writes."""
    directory = cache_dir()
    if directory is None or not directory.exists():
        return
    cutoff = time.time() - _CACHE_TTL
    try:
        for path in directory.iterdir():
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                pass
    except OSError:
        pass
