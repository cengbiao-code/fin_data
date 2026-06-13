# fin-report-extractor

Local, high-trust financial report extraction system for text-based PDFs.

## Current Work Context

**Branch**: `codex/fix-a-share-cross-page-statements`
**State**: All 9 tasks completed. 139 tests pass.

### Completed Features

| Area | Description |
|------|-------------|
| **A-share** | PdfPlumber extraction, cross-page handling, merged-header column offset fix |
| **HK market** | PyMuPDF borderless table extraction, Adobe-CNS1 CMap decoding, Big5 HK repair |
| **US market** | Label patterns (BS/IS/CF), `table_titles.yml` patterns with comprehensive income |
| **Column clustering** | Adjacent column merging + footnote absorption in `pymupdf_extractor._merge_columns()` |
| **CMap residue** | Character corrections: 蜎→及, ╱→/, 艴→' |
| **負債總額 matching** | BS exact-match-first prevents 權益及負債總額 from satisfying 負債總額 |
| **Camelot extractor** | Stub → real `flavor='stream'` with graceful ImportError degradation |
| **DuckDB pipeline** | `publish_trusted_version()`, wide-table views, CLI `publish-trusted` command |
| **Review workbook** | 7-sheet Excel with validation failures, raw tables, corrections template |

### Extraction Success

| Report | Market | Extractor | Status |
|--------|--------|-----------|--------|
| 格力电器 2025Q1 | A_share | PdfPlumber | ✅ |
| Tencent 2026Q1 | HK | PyMuPDF | ✅ |
| Meituan 2025 Annual | HK | PyMuPDF | ✅ |
| PDF Solutions 10-Q | US | PdfPlumber | ✅ |
| Apple 10-K 2025 | US | PdfPlumber | ✅ |
| PDD 20-F 2024 | US | PyMuPDF (fallback) | ✅ |

### Key Files

- `src/fin_report_extractor/statement_workbook.py` — core export + label patterns per market
- `src/fin_report_extractor/extractors/pymupdf_extractor.py` — borderless table extraction + column clustering
- `src/fin_report_extractor/extractors/pdfplumber_extractor.py` — line-based table extraction
- `src/fin_report_extractor/extractors/camelot_extractor.py` — whitespace-based extraction (stream mode)
- `src/fin_report_extractor/pdf_text_repair.py` — CMap/Big5 repair + residue correction
- `src/fin_report_extractor/table_classifier.py` — statement role classification
- `src/fin_report_extractor/trusted_publish.py` — DuckDB analytics publishing
- `src/fin_report_extractor/cli.py` — CLI entry point with PdfPlumber→PyMuPDF auto-fallback
- `rules/` — market-specific YAML rule packs (a_share, hk, us)

### Known Issues

1. **PyMuPDF zlib errors** — non-fatal warnings on some HK PDFs
2. **Column clustering edge cases** — some HK layouts may still produce too many columns
3. **PdfPlumber fragmentation** — some PDFs (e.g., PDD 20-F) produce single-row tables; relies on PyMuPDF fallback
4. **20-F reference filings** — some 20-Fs incorporate financial statements by reference (separate PDF)
5. **Camelot extractor** — depends on `camelot-py[cv]`; degrades gracefully when not installed

### Test Runner

```powershell
D:\fin_data\.venv-smoke\Scripts\python.exe -m pytest -v
```

139 tests pass.

## Before Starting a Task

Read `AGENTS.md` for workflow instructions, then `docs/README.md` and `docs/design.md` for architecture context.
