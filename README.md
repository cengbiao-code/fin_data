# Financial Report Extractor

Local high-trust extraction pipeline for text-based PDF financial reports.

MVP scope:

- local PDF registration
- SQLite audit database
- YAML market rule packs
- validation engine
- Excel review workbook flow
- DuckDB trusted analytics publishing

## MVP Commands

### Quick Start: One-Shot Three-Statement Export

```powershell
python -m fin_report_extractor.cli export-pdf-statements `
  data/raw_pdfs/格力电器：2025年一季度报告.pdf `
  --market a_share `
  --company-id 000651 `
  --company-name 格力电器 `
  --fiscal-year 2025 `
  --report-type quarterly `
  --output data/review_exports/格力电器_2025Q1_三张报表.xlsx
```

See [`docs/cli-usage.md`](docs/cli-usage.md) for the full usage guide.

### Step-by-Step Commands

Initialize local databases:

```bash
python -m fin_report_extractor.cli init-db
```

Register a local PDF:

```bash
python -m fin_report_extractor.cli import-pdf data/raw_pdfs/sample.pdf \
  --stored-pdf-path data/raw_pdfs/sample.pdf \
  --market a_share \
  --company-id 000001 \
  --company-name 示例公司 \
  --fiscal-year 2025 \
  --report-type annual
```

Export classified tables as an Excel workbook:

```bash
python -m fin_report_extractor.cli export-statements <extraction_run_id> \
  --audit-db data/db/audit.sqlite \
  --output data/review_exports/格力电器_2025Q1_三张报表.xlsx
```

One-shot pipeline (import → profile → extract → classify → export):

```bash
python -m fin_report_extractor.cli export-pdf-statements <pdf路径> \
  --market a_share \
  --company-id 000651 \
  --company-name 格力电器 \
  --fiscal-year 2025 \
  --report-type quarterly
```

## Design References

- `docs/design.md`
- `docs/specs/data-schema.md`
- `docs/specs/rule-packs.md`
- `docs/specs/review-workbook.md`
