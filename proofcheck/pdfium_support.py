"""One process-wide lock for ALL PDFium calls, including resource destruction.

PDFium is not thread-safe even for different documents. Detached PIL images may
be OCR'd concurrently; native rendering and text extraction must hold this lock.
"""
from threading import RLock

PDFIUM_LOCK = RLock()
