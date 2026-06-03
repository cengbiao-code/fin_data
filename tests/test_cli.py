import sqlite3

from fin_report_extractor.cli import main


def test_init_db_creates_audit_and_analytics_databases(tmp_path, capsys):
    audit_db = tmp_path / "nested" / "audit.sqlite"
    analytics_db = tmp_path / "nested" / "analytics.duckdb"

    main(
        [
            "init-db",
            "--audit-db",
            str(audit_db),
            "--analytics-db",
            str(analytics_db),
        ]
    )

    output = capsys.readouterr().out
    assert str(audit_db) in output
    assert str(analytics_db) in output

    sqlite_conn = sqlite3.connect(audit_db)
    try:
        audit_tables = {
            row[0]
            for row in sqlite_conn.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }
    finally:
        sqlite_conn.close()

    assert "reports" in audit_tables
    assert analytics_db.exists()


def test_import_pdf_registers_report_with_metadata(tmp_path, capsys):
    audit_db = tmp_path / "db" / "audit.sqlite"
    pdf = tmp_path / "annual-report.pdf"
    pdf.write_bytes(b"%PDF-1.4 annual report\n")

    main(
        [
            "import-pdf",
            str(pdf),
            "--audit-db",
            str(audit_db),
            "--stored-pdf-path",
            "data/raw/annual-report.pdf",
            "--market",
            "a_share",
            "--company-id",
            "000001",
            "--company-name",
            "Example Corp",
            "--fiscal-year",
            "2025",
            "--report-type",
            "annual",
        ]
    )

    report_id = capsys.readouterr().out.strip()
    assert report_id

    conn = sqlite3.connect(audit_db)
    try:
        row = conn.execute(
            """
            select report_id, stored_pdf_path, market, company_id, company_name,
                   fiscal_year, report_type
            from reports
            """
        ).fetchone()
    finally:
        conn.close()

    assert row == (
        report_id,
        "data/raw/annual-report.pdf",
        "a_share",
        "000001",
        "Example Corp",
        2025,
        "annual",
    )
