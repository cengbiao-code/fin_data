from pathlib import Path

from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db
from fin_report_extractor.extractors import ExtractedCell, ExtractedTable
from fin_report_extractor.extraction_runs import create_extraction_run, persist_raw_tables
from fin_report_extractor.import_pdf import register_pdf
from fin_report_extractor.table_classifier import classify_tables_for_run


def _setup_run(tmp_path, *, market="a_share"):
    conn = connect_audit_db(tmp_path / "audit.sqlite")
    initialize_audit_db(conn)
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample\n")
    report_id = register_pdf(
        conn,
        pdf,
        stored_pdf_path=str(pdf),
        market=market,
    )
    run_id = create_extraction_run(
        conn,
        report_id,
        extractor_versions={"pdfplumber": "test"},
    )
    return conn, report_id, run_id


def _table(text, page_number=1, table_index=0):
    return ExtractedTable(
        extractor_name="pdfplumber",
        page_number=page_number,
        table_index_on_page=table_index,
        bbox_json=None,
        cells=[
            ExtractedCell(0, 0, text, None, page_number),
            ExtractedCell(1, 0, "资产总计", None, page_number),
        ],
        quality={},
    )


def test_classify_tables_for_run_writes_statement_roles(tmp_path):
    conn, _report_id, run_id = _setup_run(tmp_path)
    try:
        persist_raw_tables(
            conn,
            conn.execute(
                "select report_id from extraction_runs where extraction_run_id = ?",
                (run_id,),
            ).fetchone()[0],
            run_id,
            [
                _table("合并资产负债表", page_number=3, table_index=0),
                _table("合并利润表", page_number=4, table_index=0),
                _table("合并现金流量表", page_number=5, table_index=0),
            ],
        )

        summary = classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

        assert summary.classified_count == 3
        assert summary.review_required_count == 0

        rows = conn.execute(
            """
            select table_role, statement_scope, classification_confidence,
                   classification_rule_id, requires_review
            from classified_tables
            order by table_role
            """
        ).fetchall()

        assert rows == [
            ("statement.balance_sheet", "consolidated", 0.95, "table_titles.statement.balance_sheet.prefer", 0),
            ("statement.cash_flow", "consolidated", 0.95, "table_titles.statement.cash_flow.prefer", 0),
            ("statement.income_statement", "consolidated", 0.95, "table_titles.statement.income_statement.prefer", 0),
        ]
    finally:
        conn.close()


def test_classify_tables_for_run_marks_parent_excluded_table_unknown(tmp_path):
    conn, report_id, run_id = _setup_run(tmp_path)
    try:
        persist_raw_tables(conn, report_id, run_id, [_table("母公司资产负债表")])

        summary = classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

        assert summary.classified_count == 1
        assert summary.review_required_count == 1

        row = conn.execute(
            """
            select table_role, statement_scope, classification_confidence,
                   classification_rule_id, requires_review
            from classified_tables
            """
        ).fetchone()

        assert row == ("unknown", "parent", 0.0, None, 1)
    finally:
        conn.close()


def test_classify_tables_for_run_replaces_existing_classifications(tmp_path):
    conn, report_id, run_id = _setup_run(tmp_path)
    try:
        persist_raw_tables(conn, report_id, run_id, [_table("合并资产负债表")])

        first = classify_tables_for_run(conn, run_id, rules_root=Path("rules"))
        second = classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

        assert first.classified_count == 1
        assert second.classified_count == 1

        row_count = conn.execute(
            "select count(*) from classified_tables where extraction_run_id = ?",
            (run_id,),
        ).fetchone()[0]
        assert row_count == 1
    finally:
        conn.close()


def test_classify_tables_cli_writes_classifications(tmp_path, capsys):
    from fin_report_extractor.cli import main

    conn, report_id, run_id = _setup_run(tmp_path)
    try:
        persist_raw_tables(conn, report_id, run_id, [_table("合并资产负债表")])
    finally:
        conn.close()

    main(
        [
            "classify-tables",
            run_id,
            "--audit-db",
            str(tmp_path / "audit.sqlite"),
            "--rules-root",
            "rules",
        ]
    )

    output = capsys.readouterr().out
    assert f"extraction_run_id={run_id}" in output
    assert "classified=1" in output
    assert "review_required=0" in output
