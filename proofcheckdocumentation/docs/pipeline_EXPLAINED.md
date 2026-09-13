# pipeline — 0.3.1 module note

run validates run options, loads selected Excel values, rejects no-data selections, extracts a PDF or image document, prepares one matcher, preserves row numbers and OCR sources, and assembles summary/meta/warnings/timings. No UI logic lives in this module.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.

## Duplicate review in 0.3.1

Summary aggregation also counts cells requiring duplicate review. Repeated cells reuse the complete matcher/auditor result; the summary still counts each selected cell. Match rate is unchanged and does not clear duplicate flags.

See [duplicate review rules](../../docs/DUPLICATES.md).
