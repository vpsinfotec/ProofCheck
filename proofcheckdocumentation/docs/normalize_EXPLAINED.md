# normalize — 0.3.0 module note

normalize remains the canonical NFKC/casefold/whitespace transformation with optional digit, punctuation and diacritic folding. normalize_with_spans additionally maps comparison characters to original character ranges for faithful snippets, including expansions and whitespace collapse.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.
