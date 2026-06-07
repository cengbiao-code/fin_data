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


def _insert_page(conn, report_id, page_number, text):
    conn.execute(
        """
        insert into pdf_pages (
          page_id, report_id, page_number, width, height, text_char_count,
          text_density, has_statement_keywords, page_text_sample
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"page-{page_number}",
            report_id,
            page_number,
            595.0,
            842.0,
            len(text),
            0.0002,
            1,
            text,
        ),
    )


def _a_share_multicolumn_row(row_index, label, current, prior=None, page_number=1):
    return [
        ExtractedCell(row_index, 0, None, None, page_number),
        ExtractedCell(row_index, 1, label, None, page_number),
        ExtractedCell(row_index, 2, None, None, page_number),
        ExtractedCell(row_index, 3, current, None, page_number),
        ExtractedCell(row_index, 4, None, None, page_number),
        ExtractedCell(row_index, 5, None, None, page_number),
        ExtractedCell(row_index, 6, prior, None, page_number),
        ExtractedCell(row_index, 7, None, None, page_number),
        ExtractedCell(row_index, 8, None, None, page_number),
    ]


def test_extract_facts_for_run_handles_a_share_multicolumn_continuation(tmp_path):
    conn = connect_audit_db(tmp_path / "audit.sqlite")
    initialize_audit_db(conn)
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample\n")
    report_id = register_pdf(
        conn,
        pdf,
        stored_pdf_path=str(pdf),
        market="a_share",
        company_id="000651",
        company_name="格力电器",
        fiscal_year=2025,
        report_type="quarterly",
    )
    _insert_page(
        conn,
        report_id,
        1,
        "珠海格力电器股份有限公司2025年第一季度报告\n1、合并资产负债表\n单位：元",
    )
    _insert_page(conn, report_id, 2, "珠海格力电器股份有限公司2025年第一季度报告")
    run_id = create_extraction_run(conn, report_id, extractor_versions={"pdfplumber": "test"})
    page_1_cells = [
        ExtractedCell(0, 0, None, None, 1),
        ExtractedCell(0, 1, "项目", None, 1),
        ExtractedCell(0, 4, "期末余额", None, 1),
        ExtractedCell(0, 7, "期初余额", None, 1),
    ]
    page_1_cells.extend(
        _a_share_multicolumn_row(1, "资产总计", "394,568,798,089.75", "368,031,704,522.86")
    )
    page_2_cells = []
    page_2_cells.extend(
        _a_share_multicolumn_row(0, "负债合计", "247,276,037,775.29", "226,518,009,574.89", 2)
    )
    page_2_cells.extend(
        _a_share_multicolumn_row(1, "所有者权益合计", "147,292,760,314.46", "141,513,694,947.97", 2)
    )
    page_2_cells.extend(
        _a_share_multicolumn_row(2, "负债和所有者权益总计", "394,568,798,089.75", "368,031,704,522.86", 2)
    )
    persist_raw_tables(
        conn,
        report_id,
        run_id,
        [
            ExtractedTable("pdfplumber", 1, 0, None, page_1_cells, {}),
            ExtractedTable("pdfplumber", 2, 0, None, page_2_cells, {}),
        ],
    )
    classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

    try:
        summary = extract_facts_for_run(conn, run_id, rules_root=Path("rules"))

        assert summary.fact_count == 4
        rows = conn.execute(
            """
            select normalized_concept_id, raw_label, raw_value, currency,
                   scale_factor, normalized_value, table_role, statement_type,
                   period_basis, column_label, page_number, fact_status
            from extracted_facts
            order by normalized_concept_id
            """
        ).fetchall()

        assert rows == [
            (
                "total_assets",
                "资产总计",
                "394,568,798,089.75",
                "CNY",
                "1",
                "394568798089.75",
                "statement.balance_sheet",
                "balance_sheet",
                "point_in_time",
                "期末余额",
                1,
                "normalized",
            ),
            (
                "total_equity",
                "所有者权益合计",
                "147,292,760,314.46",
                "CNY",
                "1",
                "147292760314.46",
                "statement.balance_sheet",
                "balance_sheet",
                "point_in_time",
                "期末余额",
                2,
                "normalized",
            ),
            (
                "total_liabilities",
                "负债合计",
                "247,276,037,775.29",
                "CNY",
                "1",
                "247276037775.29",
                "statement.balance_sheet",
                "balance_sheet",
                "point_in_time",
                "期末余额",
                2,
                "normalized",
            ),
            (
                "total_liabilities_and_equity",
                "负债和所有者权益总计",
                "394,568,798,089.75",
                "CNY",
                "1",
                "394568798089.75",
                "statement.balance_sheet",
                "balance_sheet",
                "point_in_time",
                "期末余额",
                2,
                "normalized",
            ),
        ]
    finally:
        conn.close()


def test_extract_facts_for_run_writes_income_and_cash_flow_facts(tmp_path):
    conn = connect_audit_db(tmp_path / "audit.sqlite")
    initialize_audit_db(conn)
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample\n")
    report_id = register_pdf(
        conn,
        pdf,
        stored_pdf_path=str(pdf),
        market="a_share",
        fiscal_year=2025,
        report_type="quarterly",
    )
    _insert_page(conn, report_id, 1, "2、合并利润表\n单位：元")
    _insert_page(conn, report_id, 2, "3、合并现金流量表\n单位：元")
    run_id = create_extraction_run(conn, report_id, extractor_versions={"pdfplumber": "test"})
    income_cells = [
        ExtractedCell(0, 1, "项目", None, 1),
        ExtractedCell(0, 4, "本期发生额", None, 1),
    ]
    income_cells.extend(_a_share_multicolumn_row(1, "其中：营业收入", "41,506,860,074.79"))
    income_cells.extend(_a_share_multicolumn_row(2, "五、净利润（净亏损以“－”号填列）", "5,941,618,723.39"))
    cash_cells = [
        ExtractedCell(0, 1, "项目", None, 2),
        ExtractedCell(0, 4, "本期发生额", None, 2),
    ]
    cash_cells.extend(_a_share_multicolumn_row(1, "经营活动产生的现金流量净额", "11,001,218,583.01", page_number=2))
    persist_raw_tables(
        conn,
        report_id,
        run_id,
        [
            ExtractedTable("pdfplumber", 1, 0, None, income_cells, {}),
            ExtractedTable("pdfplumber", 2, 0, None, cash_cells, {}),
        ],
    )
    classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

    try:
        summary = extract_facts_for_run(conn, run_id, rules_root=Path("rules"))

        assert summary.fact_count == 3
        rows = conn.execute(
            """
            select normalized_concept_id, statement_type, table_role, period_basis,
                   raw_label, raw_value, normalized_value, fact_status
            from extracted_facts
            order by normalized_concept_id
            """
        ).fetchall()

        assert rows == [
            (
                "net_cash_flow_from_operating",
                "cash_flow",
                "statement.cash_flow",
                "cumulative",
                "经营活动产生的现金流量净额",
                "11,001,218,583.01",
                "11001218583.01",
                "normalized",
            ),
            (
                "net_profit",
                "income_statement",
                "statement.income_statement",
                "cumulative",
                "五、净利润（净亏损以“－”号填列）",
                "5,941,618,723.39",
                "5941618723.39",
                "normalized",
            ),
            (
                "revenue",
                "income_statement",
                "statement.income_statement",
                "cumulative",
                "其中：营业收入",
                "41,506,860,074.79",
                "41506860074.79",
                "normalized",
            ),
        ]
    finally:
        conn.close()


def test_extract_facts_for_run_uses_report_unit_context_when_statement_pages_lack_unit(tmp_path):
    conn = connect_audit_db(tmp_path / "audit.sqlite")
    initialize_audit_db(conn)
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample\n")
    report_id = register_pdf(
        conn,
        pdf,
        stored_pdf_path=str(pdf),
        market="a_share",
        fiscal_year=2025,
        report_type="quarterly",
    )
    _insert_page(conn, report_id, 1, "2、合并利润表")
    _insert_page(conn, report_id, 2, "3、合并现金流量表\n单位：元")
    run_id = create_extraction_run(conn, report_id, extractor_versions={"pdfplumber": "test"})
    income_cells = [
        ExtractedCell(0, 1, "项目", None, 1),
        ExtractedCell(0, 4, "本期发生额", None, 1),
    ]
    income_cells.extend(_a_share_multicolumn_row(1, "其中：营业收入", "41,506,860,074.79"))
    persist_raw_tables(
        conn,
        report_id,
        run_id,
        [ExtractedTable("pdfplumber", 1, 0, None, income_cells, {})],
    )
    classify_tables_for_run(conn, run_id, rules_root=Path("rules"))

    try:
        summary = extract_facts_for_run(conn, run_id, rules_root=Path("rules"))

        assert summary.fact_count == 1
        assert summary.needs_review_count == 0
        row = conn.execute(
            """
            select currency, scale_factor, normalized_value, fact_status
            from extracted_facts
            """
        ).fetchone()
        assert row == ("CNY", "1", "41506860074.79", "normalized")
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
