# PDF Profiler Design

Date: 2026-06-06

## Goal

Add a PDF profiling slice that records page-level text evidence before table
classification and fact extraction.

The profiler answers three questions:

- Is this PDF text-readable enough for the MVP pipeline?
- How many pages does it have?
- Which pages contain statement-like keywords worth inspecting first?

## Scope

In scope:

- Add `fin-report profile-pdf <report_id>`.
- Read the registered report's `stored_pdf_path`.
- Use PyMuPDF (`fitz`) to inspect pages and text.
- Update `reports.page_count`, `reports.is_text_pdf`, and
  `reports.unsupported_reason`.
- Upsert `pdf_pages` rows for every page.
- Mark `has_statement_keywords` for pages containing market-appropriate
  statement keywords.

Out of scope:

- OCR.
- Table extraction.
- Table classification.
- Concept normalization.
- Unit parsing.
- Trusted publishing.

## Data Flow

```text
reports.stored_pdf_path
  -> PyMuPDF document
  -> reports profile fields
  -> pdf_pages
```

The profiler does not create an `extraction_run`; it is report-level metadata.
Each run can reuse the same page profile.

## Page Profile

Each page stores:

- 1-based `page_number`
- PDF page `width` and `height`
- `text_char_count`
- `text_density`
- `has_statement_keywords`
- `page_text_sample`

`text_density` is computed as `text_char_count / (width * height)` when page
dimensions are available.

## Text PDF Decision

A report is considered text-readable when at least one page has non-whitespace
text. If no page has text, the profiler sets:

- `is_text_pdf = 0`
- `unsupported_reason = "no_text_layer"`

If text exists, it sets:

- `is_text_pdf = 1`
- `unsupported_reason = null`

This is conservative: scanned PDFs are not passed to OCR in the MVP.

## Statement Keywords

The first implementation uses a small market-aware keyword set:

- A share: `资产负债表`, `利润表`, `现金流量表`, `合并`
- HK: `consolidated`, `statement of financial position`,
  `statement of profit or loss`, `statement of cash flows`, `綜合`
- US: `consolidated`, `balance sheets`, `statements of operations`,
  `statements of cash flows`

This can later move into YAML rules if the classifier needs richer behavior.

## CLI

```powershell
fin-report profile-pdf <report_id> --audit-db data/db/audit.sqlite
```

The command prints:

```text
report_id=<id> pages=<n> is_text_pdf=<0|1> keyword_pages=<n>
```

Unknown reports fail before profiling. Missing files fail with a clear
`FileNotFoundError` and do not change report profile fields.

## Parallel Work Notes

This slice can proceed while future table classifier tests are designed with
fake `raw_tables/raw_cells`. Real PDF smoke tests can also proceed independently
by running `import-pdf` and `extract-tables` on local sample PDFs.

## Acceptance Criteria

- Profiling an existing text PDF writes one `pdf_pages` row per page.
- Re-running the profiler replaces existing page rows for that report.
- `reports.page_count` matches the document page count.
- Text PDFs are marked `is_text_pdf = 1`.
- Image-only/no-text PDFs are marked `is_text_pdf = 0` with
  `unsupported_reason = "no_text_layer"`.
- Statement keyword pages are flagged.
- Full tests pass.
