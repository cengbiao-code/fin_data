# Pdfplumber Raw Table Extraction Design

Date: 2026-06-06

## Goal

Add the first real PDF extraction slice: an explicit CLI command that runs
`pdfplumber` against an already registered text PDF and persists raw table
evidence to the SQLite audit database.

This slice proves that the system can move from a local PDF to immutable
`raw_tables` and `raw_cells` records without claiming that any extracted value is
a trusted financial fact.

## Scope

In scope:

- Add a dedicated `fin-report extract-tables` command.
- Create a new `extraction_run` for each extraction attempt.
- Run the `PdfPlumberExtractor` adapter on the report PDF.
- Persist extracted tables into `raw_tables`.
- Persist extracted cells into `raw_cells`.
- Record run status as `succeeded` or `failed`.
- Cover the behavior with tests using fake or monkeypatched `pdfplumber`
  objects, plus SQLite persistence tests.

Out of scope for this slice:

- Table classification.
- Concept normalization.
- Unit resolution.
- Period resolution.
- Extracted financial facts.
- Cross-extractor agreement.
- Camelot implementation.
- Trusted version publishing.
- Review workbook generation from real extraction output.

## User Workflow

The user first registers a PDF:

```powershell
fin-report import-pdf data/raw_pdfs/sample.pdf --audit-db data/db/audit.sqlite --stored-pdf-path data/raw_pdfs/sample.pdf --market a_share
```

Then the user runs extraction for the registered report:

```powershell
fin-report extract-tables <report_id> --audit-db data/db/audit.sqlite
```

The command prints the new `extraction_run_id` and the number of tables and
cells persisted.

## Architecture

The new command keeps registration and extraction separate. `import-pdf` remains
responsible for content hashing and report metadata. `extract-tables` creates a
fresh run every time, so a user can rerun extraction after changing parser
settings, dependencies, or rules without changing the registered report.

The extraction flow is:

```text
reports.stored_pdf_path
  -> extraction_runs(status=running)
  -> PdfPlumberExtractor.extract_tables()
  -> raw_tables
  -> raw_cells
  -> extraction_runs(status=succeeded)
```

On failure, the run is updated to `failed` with `error_message`, and no trusted
data is produced.

## Components

### PdfPlumberExtractor

`PdfPlumberExtractor.extract_tables(pdf_path)` becomes the first real adapter.
It opens the PDF with `pdfplumber.open`, walks pages in 1-based page order, and
extracts table grids.

The adapter returns existing domain objects:

- `ExtractedTable`
- `ExtractedCell`

Cells preserve row and column positions. Text is lightly normalized only for
storage hygiene: empty strings become `None`; financial numbers, labels, units,
and punctuation are not interpreted or corrected.

### Extraction Run Helpers

New helper functions create and finish `extraction_runs`.

Each run records:

- `report_id`
- `run_started_at`
- `run_finished_at`
- `status`
- `pipeline_version`
- `rule_pack_version`
- `extractor_versions_json`
- `error_message`

For this slice, `rule_pack_version` may be a caller-provided value or a stable
placeholder because no classification or rule matching is performed.

### Raw Table Persistence

Persistence helpers write each `ExtractedTable` to `raw_tables` and each
`ExtractedCell` to `raw_cells`.

`row_count` and `column_count` are computed from the maximum observed cell
indices. `raw_table_text` is a readable reconstruction of the grid for audit and
review context only. It is not used for financial decisions.

`normalized_text` is a simple whitespace-normalized version of `raw_text`.
It must not rewrite financial values.

### CLI

`fin-report extract-tables <report_id>`:

- Opens and initializes the audit DB.
- Looks up the report.
- Uses `reports.stored_pdf_path` as the input PDF path.
- Creates a fresh extraction run.
- Runs `PdfPlumberExtractor`.
- Persists raw evidence.
- Prints a compact summary.

If the report does not exist, the command fails with a clear message. If the
stored PDF path does not exist, the command creates a failed extraction run and
reports the missing file.

## Error Handling

Errors are explicit and auditable:

- Unknown `report_id`: fail before creating a run.
- Missing PDF path: create a failed run with an error message.
- `pdfplumber` extraction exception: create or update a failed run with the
  exception message.
- Tables with no cells are ignored unless `pdfplumber` provides enough metadata
  to preserve them usefully.

The command must not insert `extracted_facts`, validation results, trusted
versions, or corrections.

## Testing

Tests should follow TDD:

- Extractor tests monkeypatch `pdfplumber.open` with fake pages and fake tables.
- Persistence tests use an in-memory or temporary SQLite audit DB.
- CLI tests register a sample report, monkeypatch the extractor, run
  `extract-tables`, and assert that `extraction_runs`, `raw_tables`, and
  `raw_cells` are populated.
- Failure tests cover unknown report IDs and missing stored PDF paths.

The full test suite must pass before claiming completion:

```powershell
D:\fin_data\.venv-smoke\Scripts\python.exe -m pytest -v
```

## Acceptance Criteria

- Running `extract-tables` for an existing report creates exactly one new
  extraction run.
- A successful run stores raw table and raw cell rows with page, grid, extractor,
  and bbox evidence.
- Re-running extraction for the same report creates a separate run.
- A failed run records `status = failed` and an `error_message`.
- No trusted or normalized financial facts are created by this slice.
- All new behavior is covered by tests.
