# matcher — 0.3.0 module note

PreparedMatcher owns normalized pages and per-run duplicate results. Exact-first search skips fuzzy scoring. Sorted pages settle ties. Short pages use a length-sensitive ratio; unrounded scores decide status. Winning fuzzy alignments use normalize_with_spans. match_value remains a single-value compatibility wrapper.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.
