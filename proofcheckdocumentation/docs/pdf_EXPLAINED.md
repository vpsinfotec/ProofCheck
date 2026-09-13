# pdf — 0.3.0 module note

PDFium is the auto-selected native text engine. PROOFCHECK_PDF_ENGINE can select pdfplumber. Native calls and cleanup hold the shared PDFIUM_LOCK. Both engines enforce page/text limits. Empty pages optionally use content-cached Tesseract output; errors become warnings.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.
