# ocr_cache — 0.3.0 module note

Cache keys include revision, configurable namespace, content hash, DPI, language and PSM. Loads validate JSON structure and TTL. Writes use unique private temporary files and atomic replacement. Web cleanup expires entries and enforces a configurable disk budget. Change namespace after OCR engine/language updates.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.
