from pathlib import Path

from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db
from fin_report_extractor.extractors import ExtractedCell, ExtractedTable
from fin_report_extractor.extraction_runs import create_extraction_run, persist_raw_tables
from fin_report_extractor.fact_extractor import extract_facts_for_run
from fin_report_extractor.import_pdf import register_pdf
from fin_report_extractor.table_classifier import classify_tables_for_run


def _setup_classified_balance_sheet(tmp_path, *, market="us"):
    conn = connect_audit_db(tmp_path / "audit.sqlite")
    initialize_audit_db(conn)
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample\n")
    report_id = register_pdf(
        conn,
        pdf,
        stored_pdf_path=str(pdf),
        market=market,
        company_id="SMOKE",
        company_name="Smoke Test Corp",
        fiscal_year=2026,
        report_type="annual",
    )
    conn.execute(
        """
        insert into pdf_pages (
          page_id, report_id, page_number, width, height, text_char_count,
          text_density, has_statement_keywords, page_text_sample
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "page-1",
            report_id,
            1,
            595.0,
            842.0,
            120,
            0.0002,
            1,
            "Consolidated Balance Sheets\nUSD thousands",
        ),
    )
    run_id = create_extraction_run(
        conn,
        report_id,
        extractor_versions={"pdfplumber": "test"},
    )
    persist_raw_tables(
        conn,
        report_id,
        run_id,
        [
            ExtractedTable(
                extractor_name="pdfplumber",
                page_number=1,
                table_index_on_page=0,
                bbox_json="[0, 0, 100, 100]",
                cells=[
                    ExtractedCell(0, 0, "Line item", None, 1),
                    ExtractedCell(0, 1, "Amount", None, 1),
                    ExtractedCell(1, 0, "Total assets", "[1, 1, 10, 2]", 1),
                    ExtractedCell(1, 1, "100", "[10, 1, 20, 2]", 1),
                    ExtractedCell(2, 0, "Total liabilities", None, 1),
                    ExtractedCell(2, 1, "40", None, 1),
                    ExtractedCell(3, 0, "Total stockholders' equity", None, 1),
                    ExtractedCell(3, 1, "60", None, 1),
                    ExtractedCell(4, 0, "Unmapped line", None, 1),
                    ExtractedCell(4, 1, "999", None, 1),
                ],
                quality={},
            )
        ],
    )
    classify_tables_for_run(conn, run_id, rules_root=Path("rules"))
    return conn, report_id, run_id


def test_extract_facts_for_run_writes_balance_sheet_facts(tmp_path):
    conn, _report_id, run_id = _setup_classified_balance_sheet(tmp_path)
    try:
        summary = extract_facts_for_run(conn, run_id, rules_root=Path("rules"))

        assert summary.fact_count == 3
        assert summary.needs_review_count == 0

        rows = conn.execute(
            """
            select normalized_concept_id, raw_label, raw_value, parsed_decimal,
                   raw_unit, currency, scale_factor, normalized_value,
                   statement_scope, statement_type, table_role, period_basis,
                   row_label, column_label, page_number, fact_status
            from extracted_facts
            order by normalized_concept_id
            """
        ).fetchall()

        assert rows == [
            (
                "total_assets",
                "Total assets",
                "100",
                "100",
                "USD thousands",
                "USD",
                "1000",
                "100000",
                "consolidated",
                "balance_sheet",
                "statement.balance_sheet",
                "point_in_time",
                "Total assets",
                "Amount",
                1,
                "normalized",
            ),
            (
                "total_equity",
                "Total stockholders' equity",
                "60",
                "60",
                "USD thousands",
                "USD",
                "1000",
                "60000",
                "consolidated",
                "balance_sheet",
                "statement.balance_sheet",
                "point_in_time",
                "Total stockholders' equity",
                "Amount",
                1,
                "normalized",
            ),
            (
                "total_liabilities",
                "Total liabilities",
                "40",
                "40",
                "USD thousands",
                "USD",
                "1000",
                "40000",
                "consolidated",
                "balance_sheet",
                "statement.balance_sheet",
                "point_in_time",
                "Total liabilities",
                "Amount",
                1,
                "normalized",
            ),
        ]
    finally:
        conn.close()


def test_extract_facts_for_run_replaces_existing_facts(tmp_path):
    conn, _report_id, run_id = _setup_classified_balance_sheet(tmp_path)
    try:
        first = extract_facts_for_run(conn, run_id, rules_root=Path("rules"))
        second = extract_facts_for_run(conn, run_id, rules_root=Path("rules"))

        assert first.fact_count == 3
        assert second.fact_count == 3
        row_count = conn.execute(
            "select count(*) from extracted_facts where extraction_run_id = ?",
            (run_id,),
        ).fetchone()[0]
        assert row_count == 3
    finally:
        conn.close()


def test_extract_facts_cli_writes_balance_sheet_facts(tmp_path, capsys):
    from fin_report_extractor.cli import main

    conn, _report_id, run_id = _setup_classified_balance_sheet(tmp_path)
    conn.close()

    main(
        [
            "extract-facts",
            run_id,
            "--audit-db",
            str(tmp_path / "audit.sqlite"),
            "--rules-root",
            "rules",
        ]
    )

    output = capsys.readouterr().out
    assert f"extraction_run_id={run_id}" in output
    assert "facts=3" in output
    assert "needs_review=0" in output
