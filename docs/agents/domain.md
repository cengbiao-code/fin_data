# Domain Docs

This is a single-context repo for a local financial report extraction system.

## Read First

- `docs/README.md`
- `docs/design.md`
- The relevant file under `docs/specs/`
- The relevant plan under `docs/plans/`

## Domain Vocabulary

Use the project's existing terms consistently:

- PDF registration
- SQLite audit database
- DuckDB analytics database
- market rule pack
- validation engine
- review workbook
- correction import
- trusted version
- trusted facts
- extractor adapter
- raw tables and raw cells

## Architectural Rules

- SQLite is the audit ledger.
- DuckDB is the trusted analytics store.
- YAML rules identify and map; Python validation computes and decides.
- Raw extraction fields are immutable.
- Corrections are append-only.
- Trusted publishing is explicit.
- AI/default analysis reads trusted data, not raw failed extraction data.

## Context and ADRs

There is currently no root `CONTEXT.md`, `CONTEXT-MAP.md`, or `docs/adr/` directory. If they are added later, read them before making architecture or domain-language changes.

