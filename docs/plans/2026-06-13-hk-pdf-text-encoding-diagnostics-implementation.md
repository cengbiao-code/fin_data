# HK PDF Text Encoding Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `fin-report inspect-pdf-fonts` plus an experimental HK Big5/CMap decoding path for diagnostic use.

**Architecture:** Keep diagnostics outside the audit/trusted data path. `pdf_font_inspector.py` produces structured findings and CLI formatting; `hk_content_decoder.py` produces candidate decoded text from bytes/content streams without writing to SQLite or DuckDB.

**Tech Stack:** Python 3.12, pytest, PyMuPDF, pdfminer.six, existing CLI patterns.

---

### Task 1: Decoder Candidate Scoring

**Files:**
- Create: `src/fin_report_extractor/hk_content_decoder.py`
- Test: `tests/test_hk_content_decoder.py`

- [ ] Write failing tests for Big5/HKSCS candidate decoding and scoring.
- [ ] Implement minimal candidate dataclass and decoder helpers.
- [ ] Verify targeted decoder tests pass.

### Task 2: Font Inspector Domain Report

**Files:**
- Create: `src/fin_report_extractor/pdf_font_inspector.py`
- Test: `tests/test_pdf_font_inspector.py`

- [ ] Write failing tests for classification from synthetic page findings.
- [ ] Implement report dataclasses, scoring, and classification.
- [ ] Add PyMuPDF-backed PDF inspection for real file paths.
- [ ] Verify targeted inspector tests pass.

### Task 3: CLI Command

**Files:**
- Modify: `src/fin_report_extractor/cli.py`
- Test: `tests/test_cli.py`

- [ ] Write failing CLI tests for text and JSON output.
- [ ] Add `inspect-pdf-fonts` parser and handler.
- [ ] Verify CLI targeted tests pass.

### Task 4: Verification

**Files:**
- Existing tests.

- [ ] Run targeted tests for new modules and CLI.
- [ ] Run full `pytest -v`.
- [ ] Confirm candidate decoded text is not persisted to audit or analytics stores.
