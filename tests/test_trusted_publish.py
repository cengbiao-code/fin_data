import uuid

import duckdb

from fin_report_extractor.analytics_db import initialize_analytics_db
from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db
from fin_report_extractor.import_pdf import register_pdf
from fin_report_extractor.extraction_runs import create_extraction_run
from fin_report_extractor.trusted_publish import (
    is_trusted_status,
    publish_trusted_version,
)


def _insert_extracted_fact(
    conn,
    report_id,
    run_id,
    *,
    fact_id=None,
    statement_type="balance_sheet",
    table_role="statement.balance_sheet",
    normalized_concept_id="total_assets",
    normalized_value="100.00",
    unit_confidence=0.99,
    fact_status="validated",
):
    if fact_id is None:
        fact_id = str(uuid.uuid4())
    # Satisfy FK constraint from raw_table_id
    conn.execute(
        "insert or ignore into raw_tables "
        "(raw_table_id, extraction_run_id, report_id, extractor_name, "
        "page_number, table_index_on_page, created_at) "
        "values (?, ?, ?, ?, ?, ?, ?)",
        ("raw-table-1", run_id, report_id, "test", 1, 0, "2026-06-13T00:00:00"),
    )
    conn.execute(
        """
        insert into extracted_facts (
          fact_id, extraction_run_id, report_id, raw_table_id,
          raw_cell_id, source_type, market, company_id,
          fiscal_year, report_type, statement_scope, statement_type,
          table_role, period_basis, raw_label,
          normalized_concept_id, mapping_confidence,
          raw_value, parsed_decimal, raw_unit, currency,
          scale_factor, normalized_value, unit_confidence,
          row_label, column_label, page_number,
          cell_bbox_json, extractor_name, extractor_confidence,
          fact_status, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fact_id,
            run_id,
            report_id,
            "raw-table-1",
            None,
            "pdf",
            "a_share",
            "000001",
            2025,
            "annual",
            "consolidated",
            statement_type,
            table_role,
            "year_end",
            "资产总计",
            normalized_concept_id,
            0.98,
            "100",
            "100",
            "元",
            "CNY",
            "1",
            normalized_value,
            unit_confidence,
            "资产总计",
            "期末余额",
            12,
            None,
            "pdfplumber",
            0.95,
            fact_status,
            "2026-06-13T00:00:00",
        ),
    )


def _setup_publishable_run(tmp_path):
    audit_path = tmp_path / "audit.sqlite"
    analytics_path = tmp_path / "analytics.duckdb"

    conn = connect_audit_db(audit_path)
    initialize_audit_db(conn)
    initialize_analytics_db(analytics_path)

    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample\n")
    report_id = register_pdf(
        conn, pdf, stored_pdf_path=str(pdf),
        market="a_share", company_id="000001", company_name="Test Corp",
        fiscal_year=2025, report_type="annual",
    )

    run_id = create_extraction_run(
        conn, report_id, extractor_versions={"pdfplumber": "1.0"},
    )

    _insert_extracted_fact(conn, report_id, run_id)
    _insert_extracted_fact(
        conn, report_id, run_id,
        fact_id=str(uuid.uuid4()),
        normalized_concept_id="total_liabilities",
        normalized_value="60.00",
    )
    _insert_extracted_fact(
        conn, report_id, run_id,
        fact_id=str(uuid.uuid4()),
        normalized_concept_id="total_equity",
        normalized_value="40.00",
    )

    conn.commit()
    return conn, analytics_path, report_id, run_id


def test_initialize_analytics_db_creates_trusted_facts_table(tmp_path):
    db_path = tmp_path / "analytics.duckdb"

    initialize_analytics_db(db_path)

    assert db_path.exists()
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
    finally:
        conn.close()

    assert "trusted_facts" in tables


def test_is_trusted_status_only_accepts_publishable_statuses():
    trusted_statuses = [
        "verified",
        "verified_with_rounding",
        "manually_confirmed",
    ]
    untrusted_statuses = [
        "raw",
        "normalized",
        "validated",
        "failed",
        "blocked_unit_unknown",
        "blocked_extractor_conflict",
        "requires_manual_review",
        "active",
    ]

    assert all(is_trusted_status(status) for status in trusted_statuses)
    assert not any(is_trusted_status(status) for status in untrusted_statuses)


def test_publish_trusted_version_writes_to_duckdb(tmp_path):
    conn, analytics_path, report_id, run_id = _setup_publishable_run(tmp_path)

    version_id = publish_trusted_version(
        conn, analytics_path, run_id,
        notes="First trusted publish",
    )

    assert version_id is not None
    assert len(version_id) > 0

    analytics_conn = duckdb.connect(str(analytics_path))
    try:
        count = analytics_conn.execute(
            "select count(*) from trusted_facts"
        ).fetchone()[0]
        assert count == 3

        rows = analytics_conn.execute(
            "select effective_concept_id, effective_value from trusted_facts "
            "order by effective_concept_id"
        ).fetchall()
        concepts = [r[0] for r in rows]
        assert "total_assets" in concepts
        assert "total_liabilities" in concepts
        assert "total_equity" in concepts
    finally:
        analytics_conn.close()


def test_publish_trusted_version_creates_wide_views(tmp_path):
    conn, analytics_path, report_id, run_id = _setup_publishable_run(tmp_path)

    publish_trusted_version(conn, analytics_path, run_id)

    analytics_conn = duckdb.connect(str(analytics_path))
    try:
        tables = {row[0] for row in analytics_conn.execute("show tables").fetchall()}
        assert "statement_wide_balance_sheet" in tables
    finally:
        analytics_conn.close()


def test_publish_trusted_version_records_sqlite_trusted_version(tmp_path):
    conn, analytics_path, report_id, run_id = _setup_publishable_run(tmp_path)

    publish_trusted_version(conn, analytics_path, run_id, notes="test publish")

    row = conn.execute(
        "select scope, status, notes from trusted_versions "
        "where extraction_run_id = ?",
        (run_id,),
    ).fetchone()
    assert row is not None
    assert row[0] == "report"
    assert row[1] == "active"
    assert row[2] == "test publish"


def test_publish_trusted_version_raises_on_no_publishable_facts(tmp_path):
    conn, analytics_path, report_id, run_id = _setup_publishable_run(tmp_path)

    # Mark all facts as "raw" (not publishable)
    conn.execute(
        "update extracted_facts set fact_status = 'raw' "
        "where extraction_run_id = ?",
        (run_id,),
    )
    conn.commit()

    import pytest

    with pytest.raises(ValueError, match="No publishable facts"):
        publish_trusted_version(conn, analytics_path, run_id)
