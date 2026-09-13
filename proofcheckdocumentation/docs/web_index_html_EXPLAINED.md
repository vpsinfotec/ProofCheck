# web_index_html — 0.3.1 module note

The offline static shell hosts Check, History, Login, theme controls, and status UI. app.js manages scoped async callbacks, inspection cancellation/sequence checks, global run state, and 100-row result pagination. package.json is only for UI/browser tests, not an application build.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.

## Duplicate review in 0.3.1

The app.js results view adds a review count, escaped findings, row badges, and a Review duplicates filter. Similarity status remains visible. Search/pagination still apply, and older history says Not recorded.

See [duplicate review rules](../../docs/DUPLICATES.md).
