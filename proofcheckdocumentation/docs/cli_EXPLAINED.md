# cli — 0.3.0 module note

CLI options adapt into the shared pipeline. inspect honors sheet and header row. check cannot overwrite inputs or reuse output paths. Page ranges are bounded before expansion. Exit codes are 0 success, 1 missing values, and 2 invalid inputs/report failures.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.
