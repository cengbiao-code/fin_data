# Table Classifier Design

Date: 2026-06-06

## Goal

Classify persisted `raw_tables` into conservative table roles using market rule
packs.

This slice turns raw table evidence into auditable `classified_tables` rows. It
does not extract financial facts or trust any numbers.

## Scope

In scope:

- Classify one extraction run at a time.
- Read report market from `reports`.
- Read raw table text and cell text from `raw_tables/raw_cells`.
- Use `rules/<market>/table_titles.yml`.
- Write `classified_tables` rows for each raw table.
- Support roles:
  - `statement.balance_sheet`
  - `statement.income_statement`
  - `statement.cash_flow`
  - `unknown`
- Infer `statement_scope` as `consolidated`, `parent`, or `unknown`.

Out of scope:

- Note role classification.
- Fact extraction.
- Concept normalization.
- Unit and period parsing.
- Trusted publishing.

## Classification Rules

For each table:

1. Combine `raw_table_text` and all `raw_cells.raw_text` into searchable text.
2. For each statement role:
   - If any `exclude` keyword is present, skip that role.
   - If an `include` keyword is present, mark it as a candidate.
   - If a `prefer` keyword is present, boost confidence.
3. Choose the highest confidence candidate.
4. If no candidate matches, classify as `unknown`.

First-pass confidence:

- `0.95` for preferred title match.
- `0.85` for include match.
- `0.0` for `unknown`.

`requires_review`:

- `0` for confidence `>= 0.95`.
- `1` otherwise.

This keeps automatic decisions conservative.

## Scope Rules

Use `scope_keywords` from the same rule file:

- `parent` keywords win over `consolidated` keywords when both are present.
- `consolidated` if consolidated keywords are present.
- `unknown` when no scope keyword is present.

Parent tables can be classified, but require review unless later workflow
explicitly asks for parent-company reporting.

## CLI

```powershell
fin-report classify-tables <extraction_run_id> --audit-db data/db/audit.sqlite --rules-root rules
```

The command prints:

```text
extraction_run_id=<id> classified=<n> review_required=<n>
```

## Acceptance Criteria

- Balance sheet, income statement, and cash flow raw tables classify from fake
  raw table evidence.
- Excluded parent-company titles do not auto-classify as consolidated statements.
- Unknown tables are persisted as `unknown`.
- Re-running classification for the same extraction run replaces old
  `classified_tables` rows.
- Full tests pass.
