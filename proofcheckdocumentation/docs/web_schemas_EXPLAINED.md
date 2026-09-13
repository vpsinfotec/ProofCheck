# web_schemas — 0.3.1 module note

Existing result fields are preserved. Health adds upload capacity and registration availability. CheckResponse adds stage timings. Credentials have length limits. HTTP error envelopes include readable strings. Consult the canonical API reference for new columns_json and option constraints.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.

## Duplicate review in 0.3.1

MatchResultModel adds occurrence_count, occurrences, repeated_words, and needs_review. SummaryModel.duplicate_review is an integer for new runs and null for old, unaudited history. Existing fields and status semantics remain stable.

See [duplicate review rules](../../docs/DUPLICATES.md).
