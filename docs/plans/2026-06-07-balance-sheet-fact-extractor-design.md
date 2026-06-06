# Balance Sheet Fact Extractor Design

Date: 2026-06-07

## Goal

Add the first conservative fact extraction slice from classified raw tables.

This slice reads `classified_tables` for `statement.balance_sheet`, maps known
line labels through `concept_aliases.yml`, resolves simple table/page units from
`unit_patterns.yml`, parses numeric value cells, and writes `extracted_facts`.

## Scope

In scope:

- Extract facts for `statement.balance_sheet` only.
- Use one extraction run at a time.
- Read report metadata from `reports`.
- Read table role and scope from `classified_tables`.
- Read raw grid evidence from `raw_cells`.
- Use exact concept aliases from the market rule pack.
- Use simple unit text matching from page/table text.
- Persist facts to `extracted_facts`.
- Add `fin-report extract-facts <extraction_run_id>`.

Out of scope:

- Income statement and cash flow facts.
- Multi-period column parsing.
- Fuzzy concept mapping.
- Complex unit conflicts.
- Validation run persistence.
- Trusted publishing.

## Table Shape

The first implementation expects a simple two-column shape:

```text
label | value
```

Rows with unmapped labels are skipped. Rows with mapped labels but unparsable
values are persisted as facts needing review with no parsed decimal.

## Status Policy

- `fact_status = normalized` when concept, value, and unit are available.
- `fact_status = needs_review` when value or unit is missing.
- `mapping_confidence` comes from the matched concept rule.
- `unit_confidence = 0.99` for matched unit text, otherwise `0.0`.

## Acceptance Criteria

- A classified balance sheet with `total_assets`, `total_liabilities`, and
  `total_equity` rows writes three facts.
- Values are parsed as Decimal strings.
- `normalized_value = parsed_decimal * scale_factor`.
- Unknown labels are skipped.
- Re-running fact extraction for the same extraction run replaces prior facts.
- Full tests pass.
