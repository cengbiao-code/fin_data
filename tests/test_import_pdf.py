from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db
from fin_report_extractor.import_pdf import compute_sha256, register_pdf


def test_compute_sha256_is_stable_for_same_pdf_content(tmp_path):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample content\n")

    assert compute_sha256(pdf) == compute_sha256(pdf)


def test_register_pdf_reuses_same_report_for_same_content(tmp_path):
    conn = connect_audit_db(tmp_path / "audit.sqlite")
    try:
        initialize_audit_db(conn)
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4 sample content\n")

        first = register_pdf(
            conn,
            pdf,
            stored_pdf_path="data/raw/sample.pdf",
            market="a_share",
        )
        second = register_pdf(
            conn,
            pdf,
            stored_pdf_path="data/raw/sample.pdf",
            market="a_share",
        )

        assert second == first
    finally:
        conn.close()


def test_register_pdf_writes_report_to_audit_db(tmp_path):
    conn = connect_audit_db(tmp_path / "audit.sqlite")
    try:
        initialize_audit_db(conn)
        pdf = tmp_path / "annual-report.pdf"
        pdf.write_bytes(b"%PDF-1.4 annual report content\n")

        report_id = register_pdf(
            conn,
            pdf,
            stored_pdf_path="data/raw/annual-report.pdf",
            market="hk",
            company_id="00001",
            company_name="Example Holdings",
            fiscal_year=2025,
            report_type="annual",
        )

        row = conn.execute(
            """
            select
              report_id, file_sha256, original_filename, stored_pdf_path,
              market, company_id, company_name, fiscal_year, report_type,
              source_type, is_text_pdf
            from reports
            where report_id = ?
            """,
            (report_id,),
        ).fetchone()

        assert row == (
            report_id,
            compute_sha256(pdf),
            "annual-report.pdf",
            "data/raw/annual-report.pdf",
            "hk",
            "00001",
            "Example Holdings",
            2025,
            "annual",
            "pdf",
            1,
        )
    finally:
        conn.close()
