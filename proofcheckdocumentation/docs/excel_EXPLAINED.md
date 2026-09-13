# excel — 0.3.0 module note

Read-only openpyxl loading rejects oversized expanded workbooks, validates headers, rejects duplicate nonblank names, deduplicates requested names, and enforces dimensions/selected cells. Inspection accepts a configurable header row. Workbook handles close in finally. Values are saved underlying values; formulas are not recalculated.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.
