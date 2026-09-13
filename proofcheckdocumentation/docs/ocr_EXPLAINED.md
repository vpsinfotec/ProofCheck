# ocr — 0.3.0 module note

Optional local Tesseract recognition uses trained models. Native PDFium rendering is locked and returns detached images. A bounded pool OCRs one small batch at a time; each page has a strategy timeout and pixel limit. Uniform blank images skip Tesseract. EXIF orientation is applied; multi-frame images are explicitly rejected.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.
