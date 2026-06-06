from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection

from fin_report_extractor.extractors import ExtractedCell, ExtractedTable, PdfPlumberExtractor


@dataclass(frozen=True)
class RawExtractionSummary:
    extraction_run_id: str
    table_count: int
    cell_count: int


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _normalize_text(raw_text: str | None) -> str | None:
    if raw_text is None:
        return None
    normalized = " ".join(raw_text.split())
    return normalized or None


def _raw_table_text(cells: list[ExtractedCell]) -> str | None:
    if not cells:
        return None

    max_row = max(cell.row_index for cell in cells)
    max_column = max(cell.column_index for cell in cells)
    grid: list[list[str]] = [
        ["" for _column in range(max_column + 1)] for _row in range(max_row + 1)
    ]
    for cell in cells:
        grid[cell.row_index][cell.column_index] = _normalize_text(cell.raw_text) or ""
    return "\n".join("\t".join(row) for row in grid)


def _grid_size(cells: list[ExtractedCell]) -> tuple[int, int]:
    if not cells:
        return (0, 0)
    return (
        max(cell.row_index for cell in cells) + 1,
        max(cell.column_index for cell in cells) + 1,
    )


def create_extraction_run(
    conn: Connection,
    report_id: str,
    *,
    pipeline_version: str = "0.1.0",
    rule_pack_version: str = "not-used",
    extractor_versions: dict[str, str] | None = None,
) -> str:
    extraction_run_id = str(uuid.uuid4())
    conn.execute(
        """
        insert into extraction_runs (
          extraction_run_id, report_id, run_started_at, status,
          pipeline_version, rule_pack_version, extractor_versions_json
        ) values (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            extraction_run_id,
            report_id,
            _utc_now_iso(),
            "running",
            pipeline_version,
            rule_pack_version,
            _json_dumps(extractor_versions or {}),
        ),
    )
    conn.commit()
    return extraction_run_id


def finish_extraction_run(
    conn: Connection,
    extraction_run_id: str,
    *,
    status: str,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        update extraction_runs
        set status = ?, run_finished_at = ?, error_message = ?
        where extraction_run_id = ?
        """,
        (status, _utc_now_iso(), error_message, extraction_run_id),
    )
    conn.commit()


def persist_raw_tables(
    conn: Connection,
    report_id: str,
    extraction_run_id: str,
    tables: list[ExtractedTable],
) -> RawExtractionSummary:
    table_count = 0
    cell_count = 0

    for table in tables:
        if not table.cells:
            continue

        row_count, column_count = _grid_size(table.cells)
        raw_table_id = str(uuid.uuid4())
        conn.execute(
            """
            insert into raw_tables (
              raw_table_id, extraction_run_id, report_id, extractor_name,
              extractor_table_id, page_number, table_index_on_page, bbox_json,
              row_count, column_count, quality_json, raw_table_text, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                raw_table_id,
                extraction_run_id,
                report_id,
                table.extractor_name,
                None,
                table.page_number,
                table.table_index_on_page,
                table.bbox_json,
                row_count,
                column_count,
                _json_dumps(table.quality),
                _raw_table_text(table.cells),
                _utc_now_iso(),
            ),
        )
        table_count += 1

        for cell in table.cells:
            conn.execute(
                """
                insert into raw_cells (
                  raw_cell_id, raw_table_id, extraction_run_id, report_id,
                  row_index, column_index, raw_text, normalized_text, bbox_json,
                  page_number, is_header_candidate, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    raw_table_id,
                    extraction_run_id,
                    report_id,
                    cell.row_index,
                    cell.column_index,
                    cell.raw_text,
                    _normalize_text(cell.raw_text),
                    cell.bbox_json,
                    cell.page_number,
                    1 if cell.row_index == 0 else 0,
                    _utc_now_iso(),
                ),
            )
            cell_count += 1

    conn.commit()
    return RawExtractionSummary(extraction_run_id, table_count, cell_count)


def _get_pdf_path_for_report(conn: Connection, report_id: str) -> Path:
    row = conn.execute(
        "select stored_pdf_path from reports where report_id = ?",
        (report_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown report_id: {report_id}")
    return Path(str(row[0]))


def extract_tables_for_report(
    conn: Connection,
    report_id: str,
    *,
    extractor: PdfPlumberExtractor | None = None,
    pipeline_version: str = "0.1.0",
    rule_pack_version: str = "not-used",
) -> RawExtractionSummary:
    pdf_path = _get_pdf_path_for_report(conn, report_id)
    extractor = extractor or PdfPlumberExtractor()
    versions = {extractor.extractor_name: "unknown"}
    run_id = create_extraction_run(
        conn,
        report_id,
        pipeline_version=pipeline_version,
        rule_pack_version=rule_pack_version,
        extractor_versions=versions,
    )

    try:
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF path does not exist: {pdf_path}")
        tables = extractor.extract_tables(pdf_path)
        summary = persist_raw_tables(conn, report_id, run_id, tables)
        finish_extraction_run(conn, run_id, status="succeeded")
        return summary
    except Exception as exc:
        finish_extraction_run(conn, run_id, status="failed", error_message=str(exc))
        raise
