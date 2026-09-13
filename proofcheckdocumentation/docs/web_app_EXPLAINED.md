# web_app — 0.3.1 module note

FastAPI synchronous routes run blocking work in the threadpool. ResourceLimitsMiddleware enforces early body/admission limits. Check/inspect validate multipart data; columns_json supports punctuation in names. Reports require authenticated ownership; generic 500s protect internal detail. Lifespan initializes storage and runs cleanup.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.

## Duplicate review in 0.3.1

Serialization exposes duplicate counts, repeated-word evidence and needs_review; persisted history includes duplicate_review. Old records deserialize with null, never a misleading zero. There is no extra extraction/OCR pass.

See [duplicate review rules](../../docs/DUPLICATES.md).
