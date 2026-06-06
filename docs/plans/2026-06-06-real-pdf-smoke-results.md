# Real PDF Smoke Results

Date: 2026-06-06

## Goal

Exercise the local command chain against generated text PDFs under
`.smoke-run/`:

```text
init-db -> import-pdf -> profile-pdf -> extract-tables -> classify-tables
```

The smoke PDFs are synthetic but real PDF files with a text layer and drawn table
lines. They are local generated artifacts and are ignored by Git.

## Environment

Commands were run from `D:\fin_data` using:

```powershell
D:\fin_data\.venv-smoke\Scripts\python.exe -m fin_report_extractor.cli
```

## Smoke 1: Title Outside Table

PDF:

```text
.smoke-run/raw/sample_statement.pdf
```

Commands:

```powershell
python -m fin_report_extractor.cli init-db --audit-db .smoke-run\db\audit.sqlite --analytics-db .smoke-run\db\analytics.duckdb
python -m fin_report_extractor.cli import-pdf .smoke-run\raw\sample_statement.pdf --audit-db .smoke-run\db\audit.sqlite --stored-pdf-path .smoke-run\raw\sample_statement.pdf --market us --company-id SMOKE --company-name "Smoke Test Corp" --fiscal-year 2026 --report-type annual
python -m fin_report_extractor.cli profile-pdf <report_id> --audit-db .smoke-run\db\audit.sqlite
python -m fin_report_extractor.cli extract-tables <report_id> --audit-db .smoke-run\db\audit.sqlite
python -m fin_report_extractor.cli classify-tables <extraction_run_id> --audit-db .smoke-run\db\audit.sqlite --rules-root rules
```

Observed output:

```text
profile-pdf: pages=1 is_text_pdf=1 keyword_pages=1
extract-tables: tables=1 cells=8
classify-tables: classified=1 review_required=1
```

Classification row:

```text
table_role=unknown
statement_scope=unknown
classification_confidence=0.0
requires_review=1
```

Finding:

`pdfplumber` extracted the grid but not the external title. The raw table text
only contained table rows:

```text
Line item    Amount
Total assets 100
Total liabilities 40
Total equity 60
```

This means the classifier needs nearby page/title context before it can classify
tables whose title sits outside the grid.

## Smoke 2: Title Inside Table

PDF:

```text
.smoke-run/raw/sample_statement_titled.pdf
```

Observed output:

```text
profile-pdf: pages=1 is_text_pdf=1 keyword_pages=1
extract-tables: tables=1 cells=10
classify-tables: classified=1 review_required=1
```

Classification row:

```text
table_role=statement.balance_sheet
statement_scope=consolidated
classification_confidence=0.85
classification_rule_id=table_titles.statement.balance_sheet.include
requires_review=1
```

Finding:

The classifier correctly identified the table as a consolidated balance sheet.
It still required review because the US rule file currently has `include`
keywords but no `prefer` keywords, so the confidence remains `0.85`.

## Follow-Up Work

- Add page-nearby title context to raw table classification.
- Consider adding `prefer` keywords to US and HK table title rules when the title
  is a high-confidence exact statement heading.
- Keep first-pass classification conservative until real report samples are
  available.
