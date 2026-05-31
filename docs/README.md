# Documentation Guide

This directory is the source of truth for the financial report extraction MVP.

## Reading Order

1. Start with [`design.md`](design.md) for product decisions, architecture, workflow, and non-goals.
2. Use [`specs/data-schema.md`](specs/data-schema.md) when implementing SQLite audit storage or DuckDB analytics storage.
3. Use [`specs/rule-packs.md`](specs/rule-packs.md) when implementing YAML market rules, concept mapping, unit handling, period handling, or validation behavior.
4. Use [`specs/review-workbook.md`](specs/review-workbook.md) when implementing Excel review export, correction import, or manual review rules.
5. Use [`plans/2026-05-31-mvp.md`](plans/2026-05-31-mvp.md) as the executable MVP task plan.

## Authority

- `design.md` defines the product and architecture decisions.
- `specs/` defines implementation contracts.
- `plans/` defines execution order and test-first implementation steps.
- `research/` is background material only. It can inform decisions, but it is not an implementation contract.
