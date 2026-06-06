# Balance Sheet Fact Extractor Results

Date: 2026-06-07

## Goal

Add the first extracted fact layer after table classification.

## Implemented

- `fin-report extract-facts <extraction_run_id>`
- `src/fin_report_extractor/fact_extractor.py`
- Exact concept alias mapping from `concept_aliases.yml`
- Simple unit matching from `unit_patterns.yml`
- Balance sheet row/value extraction from a two-column table shape
- Replacement semantics when re-running extraction for the same run

## Current Boundary

This slice only handles `statement.balance_sheet` tables. It skips unmapped
labels and does not infer multi-period columns.

It writes facts with:

- `fact_status = normalized` when concept, numeric value, currency, and scale are known.
- `fact_status = needs_review` when value or unit evidence is incomplete.

## Next Dependency

The next serial task is validation persistence: turn extracted balance sheet
facts into `FactRef` objects, run `validate_assets_equal_liabilities_plus_equity`,
and write `validation_runs/validation_results`.
