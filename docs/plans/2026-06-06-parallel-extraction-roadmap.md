# Parallel Extraction Roadmap

Date: 2026-06-06

## Goal

Keep the real PDF extraction phase parallel where the work is independent, while
preserving strict ordering for layers that depend on earlier data contracts.

## Track A: PDF Profiler

Status: active.

Deliverables:

- `profile-pdf` CLI.
- PyMuPDF page text profiling.
- `reports` profile field updates.
- `pdf_pages` upsert.
- Keyword page detection.

This track is independent from table classification because it writes report and
page metadata only.

## Track B: Table Classifier Design

Status: planned after profiler implementation starts.

Deliverables:

- Tests using fake `raw_tables/raw_cells`.
- Conservative table role scoring for:
  - `statement.balance_sheet`
  - `statement.income_statement`
  - `statement.cash_flow`
  - `unknown`
- No fact extraction yet.

This track can design against fake raw tables, but production implementation
should wait until the profiler contract is stable.

## Track C: Real PDF Smoke Samples

Status: planned.

Deliverables:

- One or two local text PDF samples.
- Manual smoke commands for:
  - `import-pdf`
  - `profile-pdf`
  - `extract-tables`
- Notes on extracted table quality and known parser limitations.

This track does not change trusted data and can run independently of classifier
implementation.

## Serial Dependencies

These tasks should not start until earlier contracts are stable:

- Fact extraction depends on table classification.
- Unit resolution depends on table and cell context.
- Validation against real facts depends on fact extraction and unit resolution.
- Trusted publishing depends on validation and manual review rules.
