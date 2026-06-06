import json

import pytest

from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db
from fin_report_extractor.extractors import ExtractedCell, ExtractedTable
from fin_report_extractor.import_pdf import register_pdf
from fin_report_extractor.extraction_runs import (
    create_extraction_run,
    extract_tables_for_report,
    finish_extraction_run,
    persist_raw_tables,
)


def _registered_report(tmp_path):
    conn = connect_audit_db(tmp_path / "audit.sqlite")
    initialize_audit_db(conn)
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample text pdf\n")
    report_id = register_pdf(
        conn,
        pdf,
        stored_pdf_path=str(pdf),
        market="a_share",
    )
    return conn, report_id, pdf


def test_create_and_finish_extraction_run_records_status(tmp_path):
    conn, report_id, _pdf = _registered_report(tmp_path)
    try:
        run_id = create_extraction_run(
            conn,
            report_id,
            pipeline_version="0.1.0",
            rule_pack_version="not-used",
            extractor_versions={"pdfplumber": "test-version"},
        )

        running = conn.execute(
            """
            select report_id, status, pipeline_version, rule_pack_version,
                   extractor_versions_json, run_finished_at, error_message
            from extraction_runs
            where extraction_run_id = ?
            """,
            (run_id,),
        ).fetchone()

        assert running[0] == report_id
        assert running[1] == "running"
        assert running[2] == "0.1.0"
        assert running[3] == "not-used"
        assert json.loads(running[4]) == {"pdfplumber": "test-version"}
        assert running[5] is None
        assert running[6] is None

        finish_extraction_run(conn, run_id, status="succeeded")

        finished = conn.execute(
            "select status, run_finished_at, error_message from extraction_runs where extraction_run_id = ?",
            (run_id,),
        ).fetchone()

        assert finished[0] == "succeeded"
        assert finished[1] is not None
        assert finished[2] is None
    finally:
        conn.close()


def test_persist_raw_tables_writes_table_and_cell_evidence(tmp_path):
    conn, report_id, _pdf = _registered_report(tmp_path)
    try:
        run_id = create_extraction_run(
            conn,
            report_id,
            pipeline_version="0.1.0",
            rule_pack_version="not-used",
            extractor_versions={"pdfplumber": "test-version"},
        )
        table = ExtractedTable(
            extractor_name="pdfplumber",
            page_number=3,
            table_index_on_page=0,
            bbox_json="[1, 2, 3, 4]",
            cells=[
                ExtractedCell(0, 0, "项目", "[1, 2, 1.5, 2.5]", 3),
                ExtractedCell(1, 1, " 100 ", None, 3),
            ],
            quality={"source": "pdfplumber"},
        )

        summary = persist_raw_tables(conn, report_id, run_id, [table])

        assert summary.table_count == 1
        assert summary.cell_count == 2

        raw_table = conn.execute(
            """
            select extractor_name, page_number, table_index_on_page, bbox_json,
                   row_count, column_count, quality_json, raw_table_text
            from raw_tables
            """
        ).fetchone()

        assert raw_table[0] == "pdfplumber"
        assert raw_table[1] == 3
        assert raw_table[2] == 0
        assert raw_table[3] == "[1, 2, 3, 4]"
        assert raw_table[4] == 2
        assert raw_table[5] == 2
        assert json.loads(raw_table[6]) == {"source": "pdfplumber"}
        assert "项目" in raw_table[7]
        assert "100" in raw_table[7]

        raw_cells = conn.execute(
            """
            select row_index, column_index, raw_text, normalized_text, bbox_json,
                   page_number, is_header_candidate
            from raw_cells
            order by row_index, column_index
            """
        ).fetchall()

        assert raw_cells == [
            (0, 0, "项目", "项目", "[1, 2, 1.5, 2.5]", 3, 1),
            (1, 1, " 100 ", "100", None, 3, 0),
        ]
    finally:
        conn.close()


def test_extract_tables_for_report_creates_new_run_each_time(tmp_path):
    conn, report_id, _pdf = _registered_report(tmp_path)

    class FakeExtractor:
        extractor_name = "pdfplumber"

        def extract_tables(self, pdf_path):
            return [
                ExtractedTable(
                    extractor_name="pdfplumber",
                    page_number=1,
                    table_index_on_page=0,
                    bbox_json=None,
                    cells=[ExtractedCell(0, 0, "项目", None, 1)],
                    quality={},
                )
            ]

    try:
        first = extract_tables_for_report(conn, report_id, extractor=FakeExtractor())
        second = extract_tables_for_report(conn, report_id, extractor=FakeExtractor())

        assert first.extraction_run_id != second.extraction_run_id
        assert first.table_count == 1
        assert second.cell_count == 1

        run_count = conn.execute("select count(*) from extraction_runs").fetchone()[0]
        table_count = conn.execute("select count(*) from raw_tables").fetchone()[0]
        assert run_count == 2
        assert table_count == 2
    finally:
        conn.close()


def test_extract_tables_for_report_rejects_unknown_report(tmp_path):
    conn = connect_audit_db(tmp_path / "audit.sqlite")
    try:
        initialize_audit_db(conn)

        with pytest.raises(ValueError, match="Unknown report_id"):
            extract_tables_for_report(conn, "missing-report")
    finally:
        conn.close()


def test_extract_tables_for_report_records_failed_run_for_missing_pdf(tmp_path):
    conn = connect_audit_db(tmp_path / "audit.sqlite")
    initialize_audit_db(conn)
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample text pdf\n")
    report_id = register_pdf(
        conn,
        pdf,
        stored_pdf_path=str(tmp_path / "missing.pdf"),
        market="a_share",
    )

    try:
        with pytest.raises(FileNotFoundError):
            extract_tables_for_report(conn, report_id)

        row = conn.execute(
            "select status, error_message from extraction_runs where report_id = ?",
            (report_id,),
        ).fetchone()

        assert row[0] == "failed"
        assert "PDF path does not exist" in row[1]
    finally:
        conn.close()
