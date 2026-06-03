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

## Design References

- `docs/design.md`
- `docs/specs/data-schema.md`
- `docs/specs/rule-packs.md`
- `docs/specs/review-workbook.md`
