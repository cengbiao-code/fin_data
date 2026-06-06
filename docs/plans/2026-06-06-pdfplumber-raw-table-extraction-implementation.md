# Pdfplumber Raw Table Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `fin-report extract-tables` so a registered PDF can produce auditable `raw_tables` and `raw_cells` rows through `pdfplumber`.

**Architecture:** Keep PDF registration separate from extraction. Each extraction command creates a new `extraction_run`, runs `PdfPlumberExtractor`, persists immutable raw evidence, and finishes the run as `succeeded` or `failed`.

**Tech Stack:** Python 3.12, SQLite, pytest, pdfplumber, existing dataclass extractor interfaces.

---

### Task 1: Raw Extraction Persistence API

**Files:**
- Create: `src/fin_report_extractor/extraction_runs.py`
- Test: `tests/test_extraction_runs.py`

- [ ] **Step 1: Write failing persistence tests**

Test creating a run, persisting one table with two cells, and finishing the run.

- [ ] **Step 2: Run targeted test to verify it fails**

Run:

```powershell
D:\fin_data\.venv-smoke\Scripts\python.exe -m pytest tests/test_extraction_runs.py -v
```

Expected: import failure for missing `fin_report_extractor.extraction_runs`.

- [ ] **Step 3: Implement minimal helpers**

Implement:

- `create_extraction_run`
- `finish_extraction_run`
- `persist_raw_tables`
- `extract_tables_for_report`

- [ ] **Step 4: Run targeted test to verify it passes**

Run the same targeted test and expect PASS.

### Task 2: PdfPlumberExtractor Adapter

**Files:**
- Modify: `src/fin_report_extractor/extractors/pdfplumber_extractor.py`
- Modify: `tests/test_extractors.py`

- [ ] **Step 1: Replace stub expectation with failing fake-pdfplumber test**

Monkeypatch `pdfplumber.open` with a fake PDF containing one page and one table.
Assert the adapter returns existing `ExtractedTable` and `ExtractedCell` objects.

- [ ] **Step 2: Run extractor test to verify it fails**

Run:

```powershell
D:\fin_data\.venv-smoke\Scripts\python.exe -m pytest tests/test_extractors.py -v
```

Expected: current stub raises `NotImplementedError`.

- [ ] **Step 3: Implement pdfplumber extraction**

Open the PDF with `pdfplumber.open`, walk pages, call `find_tables`, extract grids,
capture table bbox and cell bbox when available, and normalize empty strings to
`None`.

- [ ] **Step 4: Run extractor test to verify it passes**

Run the same targeted test and expect PASS.

### Task 3: CLI Command

**Files:**
- Modify: `src/fin_report_extractor/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI test**

Register a PDF, monkeypatch the CLI's extractor dependency, run
`extract-tables`, and assert one extraction run plus raw table/cell rows exist.

- [ ] **Step 2: Run CLI test to verify it fails**

Run:

```powershell
D:\fin_data\.venv-smoke\Scripts\python.exe -m pytest tests/test_cli.py -v
```

Expected: parser rejects unknown `extract-tables` command.

- [ ] **Step 3: Implement CLI command**

Add `extract-tables <report_id> --audit-db ...` and print a compact summary with
the run ID, table count, and cell count.

- [ ] **Step 4: Run CLI test to verify it passes**

Run the same targeted test and expect PASS.

### Task 4: Failure Paths and Full Verification

**Files:**
- Modify: `tests/test_extraction_runs.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add failure tests**

Cover unknown report IDs and missing stored PDF paths.

- [ ] **Step 2: Run targeted tests**

Run:

```powershell
D:\fin_data\.venv-smoke\Scripts\python.exe -m pytest tests/test_extraction_runs.py tests/test_cli.py tests/test_extractors.py -v
```

Expected: PASS.

- [ ] **Step 3: Run full suite**

Run:

```powershell
D:\fin_data\.venv-smoke\Scripts\python.exe -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

Commit the implementation and plan together with:

```powershell
git add docs/plans/2026-06-06-pdfplumber-raw-table-extraction-implementation.md src tests
git commit -m "feat: add pdfplumber raw table extraction"
```
