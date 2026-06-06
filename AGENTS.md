# AGENTS.md

Instructions for coding agents working in this repository.

## Project Overview

`fin-report-extractor` is a local, high-trust financial report extraction system for text-based PDF financial reports.

The MVP foundation includes:

- local PDF registration by SHA-256
- SQLite audit storage
- editable YAML market rule packs
- Python validation rules
- Excel review workbook export/import helpers
- DuckDB trusted analytics storage
- adapter-ready PDF table extractor interfaces
- a minimal `fin-report` CLI

## Start Here

Before changing code, read:

1. `docs/README.md`
2. `docs/design.md`
3. The relevant contract under `docs/specs/`
4. The relevant issue or plan section

Use `docs/plans/2026-05-31-mvp.md` as historical context for the completed MVP foundation. New extraction work should get a new plan instead of extending that MVP plan in place.

## Current Documentation Map

- `docs/design.md` defines product decisions, architecture, workflow, risks, and non-goals.
- `docs/specs/data-schema.md` defines SQLite audit storage and DuckDB analytics storage.
- `docs/specs/rule-packs.md` defines YAML market rules and validation behavior.
- `docs/specs/review-workbook.md` defines the Excel review/correction contract.
- `docs/plans/` contains executable implementation plans.
- `docs/research/` is background only, not an implementation contract.

## Agent Skills

### Issue tracker

Issues live in GitHub Issues for `cengbiao-code/fin_data`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default five-label triage vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repo. Domain docs currently live under `docs/`; no root `CONTEXT.md` or ADRs exist yet. See `docs/agents/domain.md`.

## Development Workflow

- Prefer working from a GitHub issue.
- Use one branch or worktree per issue.
- Use branch names like `codex/issue-12-short-description`.
- Keep changes scoped to the issue.
- Do not mix unrelated refactors with feature work.
- Do not recreate old documentation paths such as `docs/superpowers/plans/`.

For parallel worktrees, use project-local worktrees under `.worktrees/`; this directory is ignored by Git.

## Testing

Run the full test suite before claiming completion:

```powershell
pytest -v
```

If `pytest` is not available on PATH, use the local smoke virtualenv when present:

```powershell
D:\fin_data\.venv-smoke\Scripts\python.exe -m pytest -v
```

For targeted work, run the smallest relevant test first, then the full suite.

## CLI Smoke Checks

For changes touching the CLI, audit DB, analytics DB, or PDF registration, run a local smoke check with temporary paths:

```powershell
python -m fin_report_extractor.cli init-db --audit-db .smoke-run\db\audit.sqlite --analytics-db .smoke-run\db\analytics.duckdb
python -m fin_report_extractor.cli import-pdf .smoke-run\raw\sample.pdf --audit-db .smoke-run\db\audit.sqlite --stored-pdf-path .smoke-run\raw\sample.pdf --market a_share
```

`.smoke-run/` is ignored by Git.

## Boundaries

- Do not use LLM output as trusted financial extraction data.
- Do not auto-correct financial numbers after validation failures.
- Preserve raw extraction evidence; corrections must be append-only.
- Keep trusted data limited to `verified`, `verified_with_rounding`, and `manually_confirmed` facts.
- Real `pdfplumber` and Camelot extraction belong to the next implementation phase; the MVP foundation only scaffolds interfaces.

## Before Finishing

Check:

- tests pass
- `git status --short` is clean except intentional changes
- generated files are ignored or removed
- README/docs references use current paths
- issue acceptance criteria are covered

