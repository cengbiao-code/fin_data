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


def test_classify_tables_for_run_uses_page_text_when_title_is_outside_grid(tmp_path):
    conn, report_id, run_id = _setup_run(tmp_path, market="us")
    try:
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
                "Consolidated Balance Sheets\nLine item\nAmount",
            ),
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
                    bbox_json=None,
                    cells=[
                        ExtractedCell(0, 0, "Line item", None, 1),
                        ExtractedCell(0, 1, "Amount", None, 1),
                        ExtractedCell(1, 0, "Total assets", None, 1),
                        ExtractedCell(1, 1, "100", None, 1),
                    ],
                    quality={},
                )
            ],
        )

        summary = classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

        assert summary.classified_count == 1
        assert summary.review_required_count == 0

        row = conn.execute(
            """
            select table_role, statement_scope, classification_confidence,
                   classification_rule_id, requires_review
            from classified_tables
            """
        ).fetchone()

        assert row == (
            "statement.balance_sheet",
            "consolidated",
            0.95,
            "table_titles.statement.balance_sheet.prefer",
            0,
        )
    finally:
        conn.close()


def test_classify_tables_for_run_does_not_treat_company_name_as_parent_scope(tmp_path):
    conn, report_id, run_id = _setup_run(tmp_path)
    try:
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
                "珠海格力电器股份有限公司2025年第一季度报告\n1、合并资产负债表\n编制单位：珠海格力电器股份有限公司",
            ),
        )
        persist_raw_tables(conn, report_id, run_id, [_table("项目\n资产总计")])

        classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

        row = conn.execute(
            """
            select table_role, statement_scope, requires_review
            from classified_tables
            """
        ).fetchone()

        assert row == ("statement.balance_sheet", "consolidated", 0)
    finally:
        conn.close()


def test_classify_tables_for_run_uses_statement_line_patterns_when_title_is_missing(tmp_path):
    conn, report_id, run_id = _setup_run(tmp_path)
    try:
        persist_raw_tables(
            conn,
            report_id,
            run_id,
            [
                ExtractedTable(
                    extractor_name="pdfplumber",
                    page_number=1,
                    table_index_on_page=0,
                    bbox_json=None,
                    cells=[
                        ExtractedCell(0, 0, "项目", None, 1),
                        ExtractedCell(0, 1, "本期发生额", None, 1),
                        ExtractedCell(1, 0, "一、营业总收入", None, 1),
                        ExtractedCell(1, 1, "100", None, 1),
                    ],
                    quality={},
                ),
                ExtractedTable(
                    extractor_name="pdfplumber",
                    page_number=2,
                    table_index_on_page=0,
                    bbox_json=None,
                    cells=[
                        ExtractedCell(0, 0, "项目", None, 2),
                        ExtractedCell(0, 1, "本期发生额", None, 2),
                        ExtractedCell(1, 0, "一、经营活动产生的现金流量：", None, 2),
                        ExtractedCell(2, 0, "经营活动产生的现金流量净额", None, 2),
                        ExtractedCell(2, 1, "50", None, 2),
                    ],
                    quality={},
                ),
            ],
        )

        classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

        rows = conn.execute(
            """
            select table_role, classification_rule_id
            from classified_tables
            order by table_role
            """
        ).fetchall()

        assert rows == [
            ("statement.cash_flow", "table_titles.statement.cash_flow.content"),
            ("statement.income_statement", "table_titles.statement.income_statement.content"),
        ]
    finally:
        conn.close()


def test_classify_tables_for_run_prefers_local_table_content_over_page_context(tmp_path):
    conn, report_id, run_id = _setup_run(tmp_path)
    try:
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
                "应付账款\n负债合计\n所有者权益合计",
            ),
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
                    bbox_json=None,
                    cells=[
                        ExtractedCell(0, 0, "项目", None, 1),
                        ExtractedCell(0, 1, "本期发生额", None, 1),
                        ExtractedCell(1, 0, "一、营业总收入", None, 1),
                        ExtractedCell(2, 0, "其中：营业收入", None, 1),
                    ],
                    quality={},
                )
            ],
        )

        classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

        row = conn.execute(
            """
            select table_role, classification_rule_id
            from classified_tables
            """
        ).fetchone()

        assert row == (
            "statement.income_statement",
            "table_titles.statement.income_statement.content",
        )
    finally:
        conn.close()


def test_classify_tables_for_run_keeps_income_continuation_before_cash_flow_title(tmp_path):
    conn, report_id, run_id = _setup_run(tmp_path)
    try:
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
                "3、合并现金流量表\n单位：元\n项目\n本期发生额",
            ),
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
                    bbox_json=None,
                    cells=[
                        ExtractedCell(0, 0, "归属于少数股东的综合收益总额", None, 1),
                        ExtractedCell(0, 1, "37,533,642.69", None, 1),
                        ExtractedCell(1, 0, "八、每股收益：", None, 1),
                    ],
                    quality={},
                )
            ],
        )

        classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

        row = conn.execute(
            """
            select table_role, classification_rule_id
            from classified_tables
            """
        ).fetchone()

        assert row == (
            "statement.income_statement",
            "table_titles.statement.income_statement.content",
        )
    finally:
        conn.close()


def test_classify_tables_for_run_does_not_classify_key_metrics_summary_as_statement(tmp_path):
    conn, report_id, run_id = _setup_run(tmp_path)
    try:
        persist_raw_tables(
            conn,
            report_id,
            run_id,
            [
                ExtractedTable(
                    extractor_name="pdfplumber",
                    page_number=1,
                    table_index_on_page=0,
                    bbox_json=None,
                    cells=[
                        ExtractedCell(0, 0, "项目", None, 1),
                        ExtractedCell(0, 1, "本报告期", None, 1),
                        ExtractedCell(1, 0, "营业总收入（元）", None, 1),
                        ExtractedCell(1, 1, "100", None, 1),
                        ExtractedCell(2, 0, "归属于上市公司股东的净利润", None, 1),
                        ExtractedCell(2, 1, "40", None, 1),
                        ExtractedCell(3, 0, "经营活动产生的现金流量净额", None, 1),
                        ExtractedCell(3, 1, "50", None, 1),
                        ExtractedCell(4, 0, "基本每股收益（元/股）", None, 1),
                        ExtractedCell(4, 1, "1.07", None, 1),
                    ],
                    quality={},
                )
            ],
        )

        classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

        row = conn.execute(
            """
            select table_role, classification_confidence, classification_rule_id
            from classified_tables
            """
        ).fetchone()

        assert row == ("unknown", 0.0, None)
    finally:
        conn.close()


def test_classify_tables_for_run_prefers_hk_consolidated_statement_title(tmp_path):
    conn, report_id, run_id = _setup_run(tmp_path, market="hk")
    try:
        persist_raw_tables(
            conn,
            report_id,
            run_id,
            [_table("Consolidated statement of financial position")],
        )

        summary = classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

        assert summary.classified_count == 1
        assert summary.review_required_count == 0

        row = conn.execute(
            """
            select table_role, statement_scope, classification_confidence,
                   classification_rule_id, requires_review
            from classified_tables
            """
        ).fetchone()

        assert row == (
            "statement.balance_sheet",
            "consolidated",
            0.95,
            "table_titles.statement.balance_sheet.prefer",
            0,
        )
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
