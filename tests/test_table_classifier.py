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


def test_classify_tables_for_run_does_not_use_hk_income_page_context_for_segment_note(tmp_path):
    conn, report_id, run_id = _setup_run(tmp_path, market="hk")
    try:
        conn.execute(
            """
            insert into pdf_pages (
              page_id, report_id, page_number, width, height, text_char_count,
              text_density, has_statement_keywords, page_text_sample
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "page-24",
                report_id,
                24,
                595.0,
                842.0,
                120,
                0.0002,
                1,
                "分部資料及收入\n與簡明綜合收益表採用一致的方式計量",
            ),
        )
        persist_raw_tables(
            conn,
            report_id,
            run_id,
            [
                ExtractedTable(
                    extractor_name="pymupdf",
                    page_number=24,
                    table_index_on_page=0,
                    bbox_json=None,
                    cells=[
                        ExtractedCell(0, 0, "2", None, 24),
                        ExtractedCell(0, 1, "分部資料及收入", None, 24),
                        ExtractedCell(
                            1,
                            0,
                            "與簡明綜合收益表採用一致的方式計量",
                            None,
                            24,
                        ),
                        ExtractedCell(2, 0, "分部收入", None, 24),
                        ExtractedCell(2, 1, "196,458", None, 24),
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


def test_classify_tables_for_run_does_not_classify_hk_financial_statement_notes(tmp_path):
    conn, report_id, run_id = _setup_run(tmp_path, market="hk")
    try:
        conn.execute(
            """
            insert into pdf_pages (
              page_id, report_id, page_number, width, height, text_char_count,
              text_density, has_statement_keywords, page_text_sample
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "page-225",
                report_id,
                225,
                595.0,
                842.0,
                200,
                0.0002,
                1,
                "綜合財務報表附註\n會計政策概要\n公允價值變動於綜合收益表確認",
            ),
        )
        persist_raw_tables(
            conn,
            report_id,
            run_id,
            [
                ExtractedTable(
                    extractor_name="pymupdf",
                    page_number=225,
                    table_index_on_page=0,
                    bbox_json=None,
                    cells=[
                        ExtractedCell(0, 0, "綜合財務報表附註", None, 225),
                        ExtractedCell(1, 0, "會計政策概要", None, 225),
                        ExtractedCell(2, 0, "公允價值變動於綜合收益表確認", None, 225),
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


def test_classify_tables_for_run_does_not_classify_hk_financial_summary(tmp_path):
    conn, report_id, run_id = _setup_run(tmp_path, market="hk")
    try:
        conn.execute(
            """
            insert into pdf_pages (
              page_id, report_id, page_number, width, height, text_char_count,
              text_density, has_statement_keywords, page_text_sample
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "page-7",
                report_id,
                7,
                595.0,
                842.0,
                500,
                0.0002,
                1,
                "財務概要\n簡明綜合全面收益表\n簡明綜合財務狀況表\n總資產",
            ),
        )
        persist_raw_tables(
            conn,
            report_id,
            run_id,
            [
                ExtractedTable(
                    extractor_name="pymupdf",
                    page_number=7,
                    table_index_on_page=0,
                    bbox_json=None,
                    cells=[
                        ExtractedCell(0, 0, "財務概要", None, 7),
                        ExtractedCell(1, 0, "簡明綜合全面收益表", None, 7),
                        ExtractedCell(2, 0, "簡明綜合財務狀況表", None, 7),
                        ExtractedCell(3, 0, "總資產", None, 7),
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


def test_classify_tables_for_run_with_attributable_to_parent_line_item_not_parent_scope(tmp_path):
    """'归属于母公司所有者权益合计' is a consolidated line item, not a parent scope indicator."""
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
                "珠海格力电器股份有限公司2025年第一季度报告",
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
                        ExtractedCell(0, 1, "期末余额", None, 1),
                        ExtractedCell(1, 0, "归属于母公司所有者权益合计", None, 1),
                        ExtractedCell(1, 1, "140000000", None, 1),
                        ExtractedCell(2, 0, "负债合计", None, 1),
                        ExtractedCell(2, 1, "200000000", None, 1),
                        ExtractedCell(3, 0, "资产总计", None, 1),
                        ExtractedCell(3, 1, "340000000", None, 1),
                    ],
                    quality={},
                )
            ],
        )

        classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

        row = conn.execute(
            """
            select table_role, statement_scope, classification_confidence,
                   classification_rule_id, requires_review
            from classified_tables
            """
        ).fetchone()

        assert row[0] == "statement.balance_sheet"
        assert row[1] != "parent", (
            f"Expected scope != 'parent' but got '{row[1]}' -- "
            "'归属于母公司所有者权益合计' is a consolidated line item"
        )
    finally:
        conn.close()


def test_classify_tables_for_run_with_parent_statement_title_remains_parent(tmp_path):
    """'母公司资产负债表' in table text should still classify as parent scope."""
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
                        ExtractedCell(0, 0, "母公司资产负债表", None, 1),
                        ExtractedCell(1, 0, "资产总计", None, 1),
                    ],
                    quality={},
                )
            ],
        )

        classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

        row = conn.execute(
            """
            select table_role, statement_scope, classification_confidence,
                   classification_rule_id, requires_review
            from classified_tables
            """
        ).fetchone()

        # "母公司资产负债表" is excluded from balance_sheet role → unknown
        assert row[0] == "unknown"
        assert row[1] == "parent", f"Expected parent scope but got '{row[1]}'"
        assert row[4] == 1  # requires_review
    finally:
        conn.close()


def test_classify_tables_for_run_company_name_on_page_does_not_trigger_parent(tmp_path):
    """Company name containing '公司' should not trigger parent scope."""
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
                "珠海格力电器股份有限公司  2025年第一季度报告",
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
                        ExtractedCell(0, 1, "期末余额", None, 1),
                        ExtractedCell(1, 0, "资产总计", None, 1),
                        ExtractedCell(1, 1, "394568798089.75", None, 1),
                    ],
                    quality={},
                )
            ],
        )

        classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

        row = conn.execute(
            """
            select table_role, statement_scope, requires_review
            from classified_tables
            """
        ).fetchone()

        # Content match → balance_sheet at 0.75 confidence, scope should NOT be parent
        assert row[0] == "statement.balance_sheet"
        assert row[1] != "parent", (
            f"Company name '股份有限{chr(0x516C)}司' should not trigger parent scope"
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
