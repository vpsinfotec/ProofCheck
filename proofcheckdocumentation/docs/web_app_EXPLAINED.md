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

## Upload configuration in 0.3.2

MAX_UPLOAD_MB now accepts 1–10240 MiB, retaining its 50 MiB default. The setting is read at
import, and /api/health supplies its byte value to the UI. Restart after changing it. See
[configuration and stale-install troubleshooting](../../docs/CONFIGURATION.md). Raising
the cap does not remove page/text/pixel limits or validate multi-gigabyte processing.
