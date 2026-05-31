# Financial Report Extraction MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first local MVP foundation for a high-trust financial report extraction system: schema, rule packs, validation engine, PDF registration, review workbook flow, and trusted DuckDB publishing.

**Architecture:** Implement a Python package with clear boundaries: domain models, SQLite audit storage, YAML rule packs, validation, review workbook import/export, and DuckDB analytics publishing. PDF table extraction adapters are scaffolded behind interfaces first, so `pdfplumber`/`Camelot` implementation can follow without reshaping the data model.

**Tech Stack:** Python 3.11+, pytest, pydantic, pyyaml, pandas, openpyxl, duckdb, sqlite3, pdfplumber, camelot-py, pymupdf.

---

## Reference Documents

- `docs/research/github-component-research.md`
- `docs/design/financial-report-extraction-system-design.md`
- `docs/specs/mvp-data-schema.md`
- `docs/specs/mvp-rule-packs.md`
- `docs/specs/mvp-review-workbook.md`

## File Structure

Create this structure:

```text
pyproject.toml
README.md
src/fin_report_extractor/
  __init__.py
  cli.py
  audit_db.py
  analytics_db.py
  domain.py
  import_pdf.py
  rules.py
  validation.py
  review_workbook.py
  trusted_publish.py
  extractors/
    __init__.py
    base.py
    pdfplumber_extractor.py
    camelot_extractor.py
rules/
  a_share/
    table_titles.yml
    concept_aliases.yml
    unit_patterns.yml
    period_patterns.yml
    note_roles.yml
    validation_overrides.yml
  hk/
    table_titles.yml
    concept_aliases.yml
    unit_patterns.yml
    period_patterns.yml
    note_roles.yml
    validation_overrides.yml
  us/
    table_titles.yml
    concept_aliases.yml
    unit_patterns.yml
    period_patterns.yml
    note_roles.yml
    validation_overrides.yml
tests/
  test_audit_db.py
  test_rules.py
  test_validation.py
  test_import_pdf.py
  test_review_workbook.py
  test_trusted_publish.py
```

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/fin_report_extractor/__init__.py`
- Create: `tests/test_rules.py`

- [ ] **Step 1: Write the failing smoke test**

Create `tests/test_rules.py`:

```python
from fin_report_extractor import __version__


def test_package_imports():
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_rules.py::test_package_imports -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'fin_report_extractor'`.

- [ ] **Step 3: Create project metadata**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "fin-report-extractor"
version = "0.1.0"
description = "Local high-trust financial report extraction system"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.7",
  "pyyaml>=6.0",
  "pandas>=2.2",
  "openpyxl>=3.1",
  "duckdb>=1.0",
  "pdfplumber>=0.11",
  "pymupdf>=1.24",
]

[project.optional-dependencies]
camelot = ["camelot-py[cv]>=0.11"]
dev = ["pytest>=8.2"]

[project.scripts]
fin-report = "fin_report_extractor.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Create `README.md`:

```markdown
# Financial Report Extractor

Local high-trust extraction pipeline for text-based PDF financial reports.

MVP scope:

- local PDF registration
- SQLite audit database
- YAML market rule packs
- validation engine
- Excel review workbook flow
- DuckDB trusted analytics publishing
```

Create `src/fin_report_extractor/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_rules.py::test_package_imports -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md src/fin_report_extractor/__init__.py tests/test_rules.py
git commit -m "chore: scaffold financial report extractor project"
```

## Task 2: Domain Models

**Files:**
- Create: `src/fin_report_extractor/domain.py`
- Modify: `tests/test_validation.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_validation.py`:

```python
from decimal import Decimal

from fin_report_extractor.domain import FactRef, RuleTolerance


def test_fact_ref_keeps_decimal_value():
    fact = FactRef(
        fact_id="fact-1",
        concept_id="total_assets",
        value=Decimal("100"),
        raw_value="100",
        currency="CNY",
        scale_factor=Decimal("10000"),
        unit_confidence=0.99,
        page_number=12,
        table_role="statement.balance_sheet",
        row_label="资产总计",
        column_label="期末余额",
        cell_bbox_json="[1,2,3,4]",
    )

    assert fact.value == Decimal("100")
    assert fact.concept_id == "total_assets"


def test_rule_tolerance_defaults_are_explicit():
    tolerance = RuleTolerance(
        absolute_tolerance=Decimal("2"),
        relative_tolerance=Decimal("0.0001"),
    )

    assert tolerance.absolute_tolerance == Decimal("2")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_validation.py -v
```

Expected: FAIL with `ModuleNotFoundError` or missing `FactRef`.

- [ ] **Step 3: Implement domain models**

Create `src/fin_report_extractor/domain.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


ValidationStatus = Literal[
    "verified",
    "verified_with_rounding",
    "failed",
    "blocked_unit_unknown",
    "blocked_extractor_conflict",
    "requires_manual_review",
    "manually_confirmed",
]


@dataclass(frozen=True)
class FactRef:
    fact_id: str
    concept_id: str
    value: Decimal | None
    raw_value: str | None
    currency: str | None
    scale_factor: Decimal | None
    unit_confidence: float
    page_number: int
    table_role: str
    row_label: str | None
    column_label: str | None
    cell_bbox_json: str | None


@dataclass(frozen=True)
class RuleTolerance:
    absolute_tolerance: Decimal
    relative_tolerance: Decimal


@dataclass(frozen=True)
class ValidationResult:
    rule_id: str
    rule_name: str
    severity: Literal["error", "warning"]
    status: ValidationStatus
    lhs_value: Decimal | None
    rhs_value: Decimal | None
    difference_value: Decimal | None
    involved_fact_ids: list[str]
    message: str
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_validation.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fin_report_extractor/domain.py tests/test_validation.py
git commit -m "feat: add domain models for validation"
```

## Task 3: SQLite Audit Schema

**Files:**
- Create: `src/fin_report_extractor/audit_db.py`
- Modify: `tests/test_audit_db.py`

- [ ] **Step 1: Write failing SQLite schema tests**

Create `tests/test_audit_db.py`:

```python
import sqlite3

from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db


def test_initialize_audit_db_creates_core_tables(tmp_path):
    db_path = tmp_path / "audit.sqlite"
    conn = connect_audit_db(db_path)
    initialize_audit_db(conn)

    table_names = {
        row[0]
        for row in conn.execute(
            "select name from sqlite_master where type = 'table'"
        ).fetchall()
    }

    assert "reports" in table_names
    assert "extraction_runs" in table_names
    assert "raw_cells" in table_names
    assert "corrections" in table_names
    assert "trusted_versions" in table_names


def test_reports_file_hash_is_unique(tmp_path):
    conn = sqlite3.connect(tmp_path / "audit.sqlite")
    initialize_audit_db(conn)

    sql = """
    insert into reports (
      report_id, file_sha256, original_filename, stored_pdf_path,
      market, source_type, is_text_pdf, created_at
    ) values (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = ("r1", "abc", "a.pdf", "data/raw/a.pdf", "a_share", "pdf", 1, "2026-05-31T00:00:00")
    conn.execute(sql, params)

    try:
        conn.execute(sql, ("r2", "abc", "b.pdf", "data/raw/b.pdf", "a_share", "pdf", 1, "2026-05-31T00:00:01"))
    except sqlite3.IntegrityError:
        duplicate_blocked = True
    else:
        duplicate_blocked = False

    assert duplicate_blocked is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_audit_db.py -v
```

Expected: FAIL because `audit_db.py` does not exist.

- [ ] **Step 3: Implement audit database initialization**

Create `src/fin_report_extractor/audit_db.py` with schema matching `docs/specs/mvp-data-schema.md`. Start with the core tables required by tests:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_audit_db(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("pragma foreign_keys = on")
    return conn


def initialize_audit_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists reports (
          report_id text primary key,
          file_sha256 text not null unique,
          original_filename text not null,
          stored_pdf_path text not null,
          market text not null,
          company_id text,
          company_name text,
          fiscal_year integer,
          report_type text,
          source_type text not null,
          page_count integer,
          is_text_pdf integer not null,
          unsupported_reason text,
          created_at text not null
        );

        create index if not exists idx_reports_company_period
        on reports (market, company_id, fiscal_year, report_type);

        create table if not exists extraction_runs (
          extraction_run_id text primary key,
          report_id text not null references reports(report_id),
          run_started_at text not null,
          run_finished_at text,
          status text not null,
          pipeline_version text not null,
          rule_pack_version text not null,
          extractor_versions_json text not null,
          error_message text
        );

        create index if not exists idx_extraction_runs_report
        on extraction_runs (report_id, run_started_at);

        create table if not exists raw_tables (
          raw_table_id text primary key,
          extraction_run_id text not null references extraction_runs(extraction_run_id),
          report_id text not null references reports(report_id),
          extractor_name text not null,
          extractor_table_id text,
          page_number integer not null,
          table_index_on_page integer not null,
          bbox_json text,
          row_count integer,
          column_count integer,
          quality_json text,
          raw_table_text text,
          created_at text not null
        );

        create table if not exists raw_cells (
          raw_cell_id text primary key,
          raw_table_id text not null references raw_tables(raw_table_id),
          extraction_run_id text not null references extraction_runs(extraction_run_id),
          report_id text not null references reports(report_id),
          row_index integer not null,
          column_index integer not null,
          raw_text text,
          normalized_text text,
          bbox_json text,
          page_number integer not null,
          is_header_candidate integer not null,
          created_at text not null
        );

        create table if not exists corrections (
          correction_id text primary key,
          correction_batch_id text not null,
          fact_id text not null,
          field_name text not null,
          old_value text,
          new_value text,
          correction_reason text not null,
          created_at text not null
        );

        create table if not exists trusted_versions (
          trusted_version_id text primary key,
          report_id text not null references reports(report_id),
          extraction_run_id text not null references extraction_runs(extraction_run_id),
          scope text not null,
          scope_key text,
          status text not null,
          published_at text not null,
          published_by text,
          notes text
        );

        create unique index if not exists idx_one_active_trusted_version
        on trusted_versions(report_id, scope, coalesce(scope_key, ''))
        where status = 'active';
        """
    )
    conn.commit()
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_audit_db.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fin_report_extractor/audit_db.py tests/test_audit_db.py
git commit -m "feat: initialize SQLite audit schema"
```

## Task 4: YAML Rule Pack Loader

**Files:**
- Create: `src/fin_report_extractor/rules.py`
- Create: `rules/a_share/*.yml`
- Create: `rules/hk/*.yml`
- Create: `rules/us/*.yml`
- Modify: `tests/test_rules.py`

- [ ] **Step 1: Write failing tests for rule loading**

Replace `tests/test_rules.py` with:

```python
from pathlib import Path

from fin_report_extractor import __version__
from fin_report_extractor.rules import load_market_rule_pack


def test_package_imports():
    assert __version__ == "0.1.0"


def test_load_a_share_rule_pack():
    rule_pack = load_market_rule_pack(Path("rules"), "a_share")

    assert rule_pack.market == "a_share"
    assert "statement.balance_sheet" in rule_pack.table_titles["statement_titles"]
    assert "total_assets" in rule_pack.concept_aliases["concepts"]
    assert rule_pack.version_hash
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_rules.py -v
```

Expected: FAIL because `load_market_rule_pack` is missing.

- [ ] **Step 3: Create minimal A-share rule files**

Create `rules/a_share/table_titles.yml`, `concept_aliases.yml`, `unit_patterns.yml`, `period_patterns.yml`, `note_roles.yml`, and `validation_overrides.yml` using the examples from `docs/specs/mvp-rule-packs.md`.

- [ ] **Step 4: Create HK and US rule files**

Create equivalent minimal files under `rules/hk` and `rules/us`, using examples from `docs/specs/mvp-rule-packs.md`.

- [ ] **Step 5: Implement loader**

Create `src/fin_report_extractor/rules.py`:

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


RULE_FILENAMES = [
    "table_titles.yml",
    "concept_aliases.yml",
    "unit_patterns.yml",
    "period_patterns.yml",
    "note_roles.yml",
    "validation_overrides.yml",
]


@dataclass(frozen=True)
class MarketRulePack:
    market: str
    version_hash: str
    table_titles: dict[str, Any]
    concept_aliases: dict[str, Any]
    unit_patterns: dict[str, Any]
    period_patterns: dict[str, Any]
    note_roles: dict[str, Any]
    validation_overrides: dict[str, Any]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Rule file must contain a mapping: {path}")
    return data


def _hash_rule_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load_market_rule_pack(rules_root: Path, market: str) -> MarketRulePack:
    market_dir = rules_root / market
    paths = [market_dir / name for name in RULE_FILENAMES]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing rule files: {missing}")

    loaded = {path.name: _load_yaml(path) for path in paths}

    return MarketRulePack(
        market=market,
        version_hash=_hash_rule_files(paths),
        table_titles=loaded["table_titles.yml"],
        concept_aliases=loaded["concept_aliases.yml"],
        unit_patterns=loaded["unit_patterns.yml"],
        period_patterns=loaded["period_patterns.yml"],
        note_roles=loaded["note_roles.yml"],
        validation_overrides=loaded["validation_overrides.yml"],
    )
```

- [ ] **Step 6: Run tests**

Run:

```bash
pytest tests/test_rules.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/fin_report_extractor/rules.py rules tests/test_rules.py
git commit -m "feat: add market rule pack loader"
```

## Task 5: Validation Engine

**Files:**
- Create: `src/fin_report_extractor/validation.py`
- Modify: `tests/test_validation.py`

- [ ] **Step 1: Add failing validation tests**

Append to `tests/test_validation.py`:

```python
from fin_report_extractor.validation import validate_assets_equal_liabilities_plus_equity


def _fact(concept_id: str, value: str, fact_id: str) -> FactRef:
    return FactRef(
        fact_id=fact_id,
        concept_id=concept_id,
        value=Decimal(value),
        raw_value=value,
        currency="CNY",
        scale_factor=Decimal("1"),
        unit_confidence=0.99,
        page_number=1,
        table_role="statement.balance_sheet",
        row_label=concept_id,
        column_label="期末余额",
        cell_bbox_json="[0,0,1,1]",
    )


def test_assets_equal_liabilities_plus_equity_verified():
    result = validate_assets_equal_liabilities_plus_equity(
        {
            "total_assets": _fact("total_assets", "100", "f1"),
            "total_liabilities": _fact("total_liabilities", "60", "f2"),
            "total_equity": _fact("total_equity", "40", "f3"),
        },
        RuleTolerance(absolute_tolerance=Decimal("2"), relative_tolerance=Decimal("0.0001")),
    )

    assert result.status == "verified"


def test_assets_equal_liabilities_plus_equity_rounding():
    result = validate_assets_equal_liabilities_plus_equity(
        {
            "total_assets": _fact("total_assets", "100", "f1"),
            "total_liabilities": _fact("total_liabilities", "59", "f2"),
            "total_equity": _fact("total_equity", "40", "f3"),
        },
        RuleTolerance(absolute_tolerance=Decimal("2"), relative_tolerance=Decimal("0.0001")),
    )

    assert result.status == "verified_with_rounding"


def test_assets_equal_liabilities_plus_equity_failed():
    result = validate_assets_equal_liabilities_plus_equity(
        {
            "total_assets": _fact("total_assets", "100", "f1"),
            "total_liabilities": _fact("total_liabilities", "50", "f2"),
            "total_equity": _fact("total_equity", "40", "f3"),
        },
        RuleTolerance(absolute_tolerance=Decimal("2"), relative_tolerance=Decimal("0.0001")),
    )

    assert result.status == "failed"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_validation.py -v
```

Expected: FAIL because `validation.py` does not exist.

- [ ] **Step 3: Implement validation function**

Create `src/fin_report_extractor/validation.py`:

```python
from __future__ import annotations

from decimal import Decimal

from fin_report_extractor.domain import FactRef, RuleTolerance, ValidationResult


def validate_assets_equal_liabilities_plus_equity(
    facts: dict[str, FactRef],
    tolerance: RuleTolerance,
) -> ValidationResult:
    assets = facts.get("total_assets")
    liabilities = facts.get("total_liabilities")
    equity = facts.get("total_equity")

    present_facts = [fact for fact in [assets, liabilities, equity] if fact is not None]
    involved = [fact.fact_id for fact in present_facts]

    if assets is None or liabilities is None or equity is None:
        return ValidationResult(
            rule_id="balance_sheet.assets_equal_liabilities_plus_equity",
            rule_name="资产总计 = 负债合计 + 权益合计",
            severity="error",
            status="requires_manual_review",
            lhs_value=None,
            rhs_value=None,
            difference_value=None,
            involved_fact_ids=involved,
            message="缺少资产总计、负债合计或权益合计，无法自动校验。",
        )

    if any(f.unit_confidence < 0.95 or f.scale_factor is None for f in [assets, liabilities, equity]):
        return ValidationResult(
            rule_id="balance_sheet.assets_equal_liabilities_plus_equity",
            rule_name="资产总计 = 负债合计 + 权益合计",
            severity="error",
            status="blocked_unit_unknown",
            lhs_value=None,
            rhs_value=None,
            difference_value=None,
            involved_fact_ids=involved,
            message="相关数值存在单位不明确，不能进入可信库。",
        )

    if assets.value is None or liabilities.value is None or equity.value is None:
        return ValidationResult(
            rule_id="balance_sheet.assets_equal_liabilities_plus_equity",
            rule_name="资产总计 = 负债合计 + 权益合计",
            severity="error",
            status="requires_manual_review",
            lhs_value=None,
            rhs_value=None,
            difference_value=None,
            involved_fact_ids=involved,
            message="相关数值缺少可计算金额，无法自动校验。",
        )

    lhs = assets.value
    rhs = liabilities.value + equity.value
    diff = lhs - rhs

    if diff == Decimal("0"):
        status = "verified"
    elif abs(diff) <= tolerance.absolute_tolerance:
        status = "verified_with_rounding"
    elif lhs != 0 and abs(diff / lhs) <= tolerance.relative_tolerance:
        status = "verified_with_rounding"
    else:
        status = "failed"

    return ValidationResult(
        rule_id="balance_sheet.assets_equal_liabilities_plus_equity",
        rule_name="资产总计 = 负债合计 + 权益合计",
        severity="error",
        status=status,
        lhs_value=lhs,
        rhs_value=rhs,
        difference_value=diff,
        involved_fact_ids=involved,
        message=f"资产总计 {lhs}，负债+权益 {rhs}，差异 {diff}。",
    )
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_validation.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fin_report_extractor/validation.py tests/test_validation.py
git commit -m "feat: add balance sheet validation rule"
```

## Task 6: Local PDF Registration

**Files:**
- Create: `src/fin_report_extractor/import_pdf.py`
- Modify: `tests/test_import_pdf.py`

- [ ] **Step 1: Write failing PDF registration tests**

Create `tests/test_import_pdf.py`:

```python
from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db
from fin_report_extractor.import_pdf import compute_sha256, register_pdf


def test_compute_sha256_is_stable(tmp_path):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample")

    assert compute_sha256(pdf) == compute_sha256(pdf)


def test_register_pdf_reuses_same_report_for_same_hash(tmp_path):
    conn = connect_audit_db(tmp_path / "audit.sqlite")
    initialize_audit_db(conn)
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample")

    first = register_pdf(conn, pdf, stored_pdf_path="data/raw/sample.pdf", market="a_share")
    second = register_pdf(conn, pdf, stored_pdf_path="data/raw/sample.pdf", market="a_share")

    assert first == second
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_import_pdf.py -v
```

Expected: FAIL because `import_pdf.py` does not exist.

- [ ] **Step 3: Implement PDF registration**

Create `src/fin_report_extractor/import_pdf.py`:

```python
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Connection


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def compute_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register_pdf(
    conn: Connection,
    pdf_path: str | Path,
    *,
    stored_pdf_path: str,
    market: str,
    company_id: str | None = None,
    company_name: str | None = None,
    fiscal_year: int | None = None,
    report_type: str | None = None,
    is_text_pdf: bool = True,
    unsupported_reason: str | None = None,
) -> str:
    pdf_path = Path(pdf_path)
    file_sha256 = compute_sha256(pdf_path)

    existing = conn.execute(
        "select report_id from reports where file_sha256 = ?",
        (file_sha256,),
    ).fetchone()
    if existing:
        return str(existing[0])

    report_id = str(uuid.uuid4())
    conn.execute(
        """
        insert into reports (
          report_id, file_sha256, original_filename, stored_pdf_path,
          market, company_id, company_name, fiscal_year, report_type,
          source_type, is_text_pdf, unsupported_reason, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            report_id,
            file_sha256,
            pdf_path.name,
            stored_pdf_path,
            market,
            company_id,
            company_name,
            fiscal_year,
            report_type,
            "pdf",
            1 if is_text_pdf else 0,
            unsupported_reason,
            utc_now_iso(),
        ),
    )
    conn.commit()
    return report_id
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_import_pdf.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fin_report_extractor/import_pdf.py tests/test_import_pdf.py
git commit -m "feat: register local PDFs by content hash"
```

## Task 7: Review Workbook Export/Import Contract

**Files:**
- Create: `src/fin_report_extractor/review_workbook.py`
- Modify: `tests/test_review_workbook.py`

- [ ] **Step 1: Write failing workbook tests**

Create `tests/test_review_workbook.py`:

```python
from openpyxl import load_workbook

from fin_report_extractor.review_workbook import export_review_workbook, read_corrections


def test_export_review_workbook_creates_required_sheets(tmp_path):
    path = tmp_path / "review.xlsx"

    export_review_workbook(
        path,
        metadata={
            "workbook_schema_version": "1",
            "report_id": "report-1",
            "extraction_run_id": "run-1",
            "review_export_id": "review-1",
            "rule_pack_version": "rules-1",
            "exported_at": "2026-05-31T00:00:00Z",
        },
        failures=[],
        raw_rows=[],
    )

    wb = load_workbook(path)
    assert "summary" in wb.sheetnames
    assert "validation_failures" in wb.sheetnames
    assert "corrections" in wb.sheetnames
    assert "_metadata" in wb.sheetnames


def test_read_corrections_reads_user_rows(tmp_path):
    path = tmp_path / "review.xlsx"
    export_review_workbook(
        path,
        metadata={
            "workbook_schema_version": "1",
            "report_id": "report-1",
            "extraction_run_id": "run-1",
            "review_export_id": "review-1",
            "rule_pack_version": "rules-1",
            "exported_at": "2026-05-31T00:00:00Z",
        },
        failures=[],
        raw_rows=[],
    )
    wb = load_workbook(path)
    ws = wb["corrections"]
    ws.append(["fact-1", "confirm", None, None, None, None, None, None, "人工确认"])
    wb.save(path)

    rows = read_corrections(path)

    assert rows[0]["fact_id"] == "fact-1"
    assert rows[0]["correction_action"] == "confirm"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_review_workbook.py -v
```

Expected: FAIL because `review_workbook.py` does not exist.

- [ ] **Step 3: Implement workbook export/import helpers**

Create `src/fin_report_extractor/review_workbook.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook


CORRECTION_COLUMNS = [
    "fact_id",
    "correction_action",
    "corrected_value",
    "corrected_unit",
    "normalized_concept_id",
    "period_basis",
    "statement_scope",
    "table_role",
    "correction_reason",
]


def export_review_workbook(
    path: str | Path,
    *,
    metadata: dict[str, str],
    failures: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
) -> None:
    wb = Workbook()
    wb.remove(wb.active)

    summary = wb.create_sheet("summary")
    summary.append(["field", "value"])
    for key, value in metadata.items():
        summary.append([key, value])

    failures_ws = wb.create_sheet("validation_failures")
    failure_columns = [
        "validation_result_id",
        "rule_id",
        "severity",
        "status",
        "message",
        "involved_fact_ids",
        "lhs_value",
        "rhs_value",
        "difference_value",
        "source_pages",
        "suggested_action",
    ]
    failures_ws.append(failure_columns)
    for row in failures:
        failures_ws.append([row.get(column) for column in failure_columns])

    for sheet_name in ["balance_sheet_raw", "income_statement_raw", "cash_flow_raw", "notes_revenue_raw"]:
        ws = wb.create_sheet(sheet_name)
        columns = [
            "fact_id",
            "raw_table_id",
            "raw_cell_id",
            "extractor_name",
            "page_number",
            "table_index_on_page",
            "row_index",
            "column_index",
            "cell_bbox_json",
            "table_role",
            "statement_scope",
            "period_basis",
            "raw_label",
            "normalized_concept_id",
            "raw_value",
            "raw_unit",
            "currency",
            "scale_factor",
            "normalized_value",
            "validation_status",
            "review_hint",
        ]
        ws.append(columns)
        for row in raw_rows:
            if row.get("target_sheet") == sheet_name:
                ws.append([row.get(column) for column in columns])

    corrections = wb.create_sheet("corrections")
    corrections.append(CORRECTION_COLUMNS)

    metadata_ws = wb.create_sheet("_metadata")
    metadata_ws.append(["key", "value"])
    for key, value in metadata.items():
        metadata_ws.append([key, value])

    wb.save(path)


def read_corrections(path: str | Path) -> list[dict[str, Any]]:
    wb = load_workbook(path)
    ws = wb["corrections"]
    headers = [cell.value for cell in ws[1]]
    rows: list[dict[str, Any]] = []
    for values in ws.iter_rows(min_row=2, values_only=True):
        if all(value is None for value in values):
            continue
        row = dict(zip(headers, values))
        rows.append(row)
    return rows
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_review_workbook.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fin_report_extractor/review_workbook.py tests/test_review_workbook.py
git commit -m "feat: add review workbook contract"
```

## Task 8: DuckDB Trusted Publishing

**Files:**
- Create: `src/fin_report_extractor/analytics_db.py`
- Create: `src/fin_report_extractor/trusted_publish.py`
- Modify: `tests/test_trusted_publish.py`

- [ ] **Step 1: Write failing DuckDB publishing test**

Create `tests/test_trusted_publish.py`:

```python
import duckdb

from fin_report_extractor.analytics_db import initialize_analytics_db


def test_initialize_analytics_db_creates_trusted_facts(tmp_path):
    db_path = tmp_path / "analytics.duckdb"
    initialize_analytics_db(db_path)

    conn = duckdb.connect(str(db_path))
    tables = {row[0] for row in conn.execute("show tables").fetchall()}

    assert "trusted_facts" in tables
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest tests/test_trusted_publish.py -v
```

Expected: FAIL because `analytics_db.py` does not exist.

- [ ] **Step 3: Implement DuckDB schema initialization**

Create `src/fin_report_extractor/analytics_db.py`:

```python
from __future__ import annotations

from pathlib import Path

import duckdb


def initialize_analytics_db(path: str | Path) -> None:
    conn = duckdb.connect(str(path))
    conn.execute(
        """
        create table if not exists trusted_facts (
          trusted_version_id varchar,
          fact_id varchar,
          report_id varchar,
          extraction_run_id varchar,
          company_id varchar,
          company_name varchar,
          market varchar,
          fiscal_year integer,
          report_type varchar,
          statement_scope varchar,
          statement_type varchar,
          table_role varchar,
          period_basis varchar,
          period_end date,
          instant_date date,
          effective_concept_id varchar,
          raw_label varchar,
          effective_value decimal(38, 6),
          effective_unit varchar,
          currency varchar,
          source_page integer,
          trusted_status varchar
        )
        """
    )
    conn.close()
```

Create `src/fin_report_extractor/trusted_publish.py`:

```python
from __future__ import annotations

TRUSTED_STATUSES = {"verified", "verified_with_rounding", "manually_confirmed"}


def is_trusted_status(status: str) -> bool:
    return status in TRUSTED_STATUSES
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_trusted_publish.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fin_report_extractor/analytics_db.py src/fin_report_extractor/trusted_publish.py tests/test_trusted_publish.py
git commit -m "feat: initialize DuckDB trusted analytics schema"
```

## Task 9: Extractor Interfaces

**Files:**
- Create: `src/fin_report_extractor/extractors/__init__.py`
- Create: `src/fin_report_extractor/extractors/base.py`
- Create: `src/fin_report_extractor/extractors/pdfplumber_extractor.py`
- Create: `src/fin_report_extractor/extractors/camelot_extractor.py`

- [ ] **Step 1: Add extractor interface**

Create `src/fin_report_extractor/extractors/base.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExtractedCell:
    row_index: int
    column_index: int
    raw_text: str | None
    bbox_json: str | None
    page_number: int


@dataclass(frozen=True)
class ExtractedTable:
    extractor_name: str
    page_number: int
    table_index_on_page: int
    bbox_json: str | None
    cells: list[ExtractedCell]
    quality: dict[str, object]


class TableExtractor:
    extractor_name: str

    def extract_tables(self, pdf_path: Path) -> list[ExtractedTable]:
        raise NotImplementedError
```

- [ ] **Step 2: Add stub adapters that fail clearly**

Create `src/fin_report_extractor/extractors/pdfplumber_extractor.py`:

```python
from __future__ import annotations

from pathlib import Path

from fin_report_extractor.extractors.base import ExtractedTable, TableExtractor


class PdfPlumberExtractor(TableExtractor):
    extractor_name = "pdfplumber"

    def extract_tables(self, pdf_path: Path) -> list[ExtractedTable]:
        raise NotImplementedError("pdfplumber table extraction is implemented after the MVP schema foundation.")
```

Create `src/fin_report_extractor/extractors/camelot_extractor.py`:

```python
from __future__ import annotations

from pathlib import Path

from fin_report_extractor.extractors.base import ExtractedTable, TableExtractor


class CamelotExtractor(TableExtractor):
    extractor_name = "camelot"

    def extract_tables(self, pdf_path: Path) -> list[ExtractedTable]:
        raise NotImplementedError("Camelot table extraction is implemented after the MVP schema foundation.")
```

Create `src/fin_report_extractor/extractors/__init__.py`:

```python
from fin_report_extractor.extractors.base import ExtractedCell, ExtractedTable, TableExtractor
from fin_report_extractor.extractors.camelot_extractor import CamelotExtractor
from fin_report_extractor.extractors.pdfplumber_extractor import PdfPlumberExtractor

__all__ = [
    "CamelotExtractor",
    "ExtractedCell",
    "ExtractedTable",
    "PdfPlumberExtractor",
    "TableExtractor",
]
```

- [ ] **Step 3: Run full tests**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/fin_report_extractor/extractors
git commit -m "feat: add table extractor interfaces"
```

## Task 10: CLI Entry Point

**Files:**
- Create: `src/fin_report_extractor/cli.py`

- [ ] **Step 1: Implement minimal CLI**

Create `src/fin_report_extractor/cli.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from fin_report_extractor.analytics_db import initialize_analytics_db
from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db
from fin_report_extractor.import_pdf import register_pdf


def main() -> None:
    parser = argparse.ArgumentParser(prog="fin-report")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db")
    init_db.add_argument("--audit-db", default="data/db/audit.sqlite")
    init_db.add_argument("--analytics-db", default="data/db/analytics.duckdb")

    import_pdf = subparsers.add_parser("import-pdf")
    import_pdf.add_argument("pdf_path")
    import_pdf.add_argument("--audit-db", default="data/db/audit.sqlite")
    import_pdf.add_argument("--stored-pdf-path", required=True)
    import_pdf.add_argument("--market", required=True)
    import_pdf.add_argument("--company-id")
    import_pdf.add_argument("--company-name")
    import_pdf.add_argument("--fiscal-year", type=int)
    import_pdf.add_argument("--report-type")

    args = parser.parse_args()

    if args.command == "init-db":
        audit_path = Path(args.audit_db)
        analytics_path = Path(args.analytics_db)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        analytics_path.parent.mkdir(parents=True, exist_ok=True)
        conn = connect_audit_db(audit_path)
        initialize_audit_db(conn)
        initialize_analytics_db(analytics_path)
        print(f"Initialized {audit_path} and {analytics_path}")
        return

    if args.command == "import-pdf":
        conn = connect_audit_db(args.audit_db)
        initialize_audit_db(conn)
        report_id = register_pdf(
            conn,
            args.pdf_path,
            stored_pdf_path=args.stored_pdf_path,
            market=args.market,
            company_id=args.company_id,
            company_name=args.company_name,
            fiscal_year=args.fiscal_year,
            report_type=args.report_type,
        )
        print(report_id)
        return
```

- [ ] **Step 2: Run CLI manually**

Run:

```bash
python -m fin_report_extractor.cli init-db --audit-db data/db/audit.sqlite --analytics-db data/db/analytics.duckdb
```

Expected: prints initialized database paths.

- [ ] **Step 3: Run full tests**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/fin_report_extractor/cli.py
git commit -m "feat: add MVP CLI entry point"
```

## Task 11: Self-Review and Documentation Alignment

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README with commands**

Append to `README.md`:

```markdown
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

- `docs/design/financial-report-extraction-system-design.md`
- `docs/specs/mvp-data-schema.md`
- `docs/specs/mvp-rule-packs.md`
- `docs/specs/mvp-review-workbook.md`
```

- [ ] **Step 2: Run full verification**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 3: Search for unresolved markers**

Run:

```bash
$pattern = 'T' + 'BD|TO' + 'DO|FIX' + 'ME|UNRESOLVED'; rg -n $pattern src tests docs README.md
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document MVP commands"
```

## Completion Criteria

The MVP foundation is complete when:

- `pytest -v` passes.
- `fin-report init-db` creates SQLite and DuckDB files.
- `register_pdf` deduplicates by SHA-256.
- Rule packs load and produce stable version hashes.
- The balance sheet validation rule returns `verified`, `verified_with_rounding`, `failed`, `blocked_unit_unknown`, and `requires_manual_review` correctly.
- Review workbook export creates all required sheets.
- Correction rows can be read from the workbook.
- DuckDB `trusted_facts` table exists.
- Extractor adapters have a stable interface for future `pdfplumber` and `Camelot` implementations.

## Planned Follow-Up After This MVP Foundation

Next implementation plan should cover:

- real `pdfplumber` table extraction,
- real `Camelot` table extraction,
- statement page detection,
- table classification,
- concept normalization,
- unit resolution,
- writing raw tables/cells/facts into SQLite,
- validation result persistence,
- trusted version publishing from SQLite to DuckDB.
