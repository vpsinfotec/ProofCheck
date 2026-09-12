# report_xlsx — 0.3.0 module note

RunResult is rendered as a summary and per-column sheets. Input strings are sanitized for illegal XML characters and explicitly stored as strings, preventing formula interpretation. Sheet titles are sanitized, truncated, and allocated uniquely. Data sheets freeze headers and expose filters.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.
