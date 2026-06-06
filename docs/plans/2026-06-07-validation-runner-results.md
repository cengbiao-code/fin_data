# Validation Runner Results

Date: 2026-06-07

## Goal

Persist validation output for extracted balance sheet facts.

## Implemented

- `fin-report validate-run <extraction_run_id>`
- `src/fin_report_extractor/validation_runner.py`
- Creation of `validation_runs`
- Persistence of `validation_results`
- Balance sheet rule:
  `balance_sheet.assets_equal_liabilities_plus_equity`

## Current Boundary

This runner validates extracted balance sheet facts only. It does not yet update
trusted versions or export review workbooks from validation failures.

## Next Dependency

The next task is to connect validation results to review export and trusted
publishing decisions.
