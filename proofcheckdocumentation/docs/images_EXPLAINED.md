# images — 0.3.0 module note

A single image or a filename-sorted folder is converted to PdfText. Cached text is read before checking engine availability. Recognition failures are warned and never cached as successes. Only actual supported files are included, and page/text limits apply.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.
