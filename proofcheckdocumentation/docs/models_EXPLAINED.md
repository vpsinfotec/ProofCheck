# models — 0.3.1 module note

Dataclasses remain the internal pipeline contract. RunResult now includes timings in seconds. MatchResult keeps original row/value, status, page, snippet, score, diff, and source. PreparedMatcher returns independent row/diff objects even when duplicate work is reused.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.

## Duplicate review in 0.3.1

MatchResult adds occurrences and repeated_words, with computed occurrence_count and needs_review properties. PageOccurrences and RepeatedWord entries are immutable. Summary.duplicate_review counts flagged cells independently of similarity status.

See [duplicate review rules](../../docs/DUPLICATES.md).
