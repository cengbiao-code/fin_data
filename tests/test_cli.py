import sqlite3

from fin_report_extractor.extractors import ExtractedCell, ExtractedTable
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


def test_extract_tables_persists_raw_tables_for_registered_report(
    tmp_path, capsys, monkeypatch
):
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
            str(pdf),
            "--market",
            "a_share",
        ]
    )
    report_id = capsys.readouterr().out.strip()

    class FakeExtractor:
        extractor_name = "pdfplumber"

        def extract_tables(self, pdf_path):
            assert pdf_path == pdf
            return [
                ExtractedTable(
                    extractor_name="pdfplumber",
                    page_number=1,
                    table_index_on_page=0,
                    bbox_json="[0, 0, 10, 10]",
                    cells=[
                        ExtractedCell(0, 0, "项目", None, 1),
                        ExtractedCell(0, 1, "金额", None, 1),
                    ],
                    quality={},
                )
            ]

    monkeypatch.setattr(
        "fin_report_extractor.cli.PdfPlumberExtractor",
        lambda: FakeExtractor(),
    )

    main(["extract-tables", report_id, "--audit-db", str(audit_db)])

    output = capsys.readouterr().out
    assert "extraction_run_id=" in output
    assert "tables=1" in output
    assert "cells=2" in output

    conn = sqlite3.connect(audit_db)
    try:
        run_count = conn.execute("select count(*) from extraction_runs").fetchone()[0]
        table_count = conn.execute("select count(*) from raw_tables").fetchone()[0]
        cell_count = conn.execute("select count(*) from raw_cells").fetchone()[0]
    finally:
        conn.close()

    assert run_count == 1
    assert table_count == 1
    assert cell_count == 2
