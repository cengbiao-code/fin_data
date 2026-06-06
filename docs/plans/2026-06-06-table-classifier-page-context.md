# Table Classifier Page Context Update

Date: 2026-06-06

## Goal

Improve table classification when the statement title appears outside the
extracted table grid.

## Change

The classifier now combines three evidence sources before matching table title
rules:

1. `pdf_pages.page_text_sample` for the table page.
2. `raw_tables.raw_table_text`.
3. `raw_cells.raw_text`.

This fixes the smoke case where `pdfplumber` extracted table rows but left the
external heading out of `raw_table_text`.

## Boundary

This does not infer facts, units, or periods. It only improves
`classified_tables` role and scope decisions.

The confidence policy stays conservative:

- `prefer` match: `0.95`
- `include` match: `0.85`
- unknown: `0.0`

US balance sheet smoke now classifies correctly when the page sample contains
`Consolidated Balance Sheets`, but it still requires review because the US rule
file has no `prefer` keywords yet.
