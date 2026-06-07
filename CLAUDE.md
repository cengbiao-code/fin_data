# fin-report-extractor

Local, high-trust financial report extraction system for text-based PDFs.

## Current Work Context

**Branch**: `codex/fix-a-share-cross-page-statements`
**Fixed**: A-share PDF table header column offset caused by merged header cells.

The fix adds `_adjust_columns_from_data()` in `statement_workbook.py` that verifies header-detected columns against actual data values — if column 4 header says "期末余额" but the numeric data lives at column 3, the function walks offsets until it finds real numbers.

**Key files**:
- `src/fin_report_extractor/statement_workbook.py` — core export logic
- `tests/test_statement_workbook.py` — 30 tests (added 6 for the column offset fix)

**Test runner**: `D:\fin_data\.venv-smoke\Scripts\python.exe -m pytest -v` — 95 tests pass.

## Cross-Page Handling

A-share financial statements often span multiple pages. Key patterns:
1. **Continuation pages may have different column widths** — the cash flow continuation (page 9) has only 5 columns vs 9 on the main table (page 8). Known issue: prior-value column may not exist on continuation pages.
2. **Section header rows** (e.g. "流动资产：") contain no numeric values and are skipped during column verification.
3. **Multiple page groups** (parent scope + consolidated scope) are merged in `export_statement_workbook` — duplicate headers are dropped, data rows appended.

## Smoke Test

格力电器 2025Q1 quarterly report (000651). One-shot command:
```
python -m fin_report_extractor.cli export-pdf-statements "data/raw_pdfs/格力电器：2025年一季度报告.pdf" --market a_share --company-id 000651 --company-name 格力电器 --fiscal-year 2025 --report-type quarterly
```

## Before Starting a Task

Read `AGENTS.md` for workflow instructions, then `docs/README.md` and `docs/design.md` for architecture context.
