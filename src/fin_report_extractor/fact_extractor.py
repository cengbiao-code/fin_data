from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from sqlite3 import Connection
from typing import Any

from fin_report_extractor.rules import load_market_rule_pack


@dataclass(frozen=True)
class FactExtractionSummary:
    extraction_run_id: str
    fact_count: int
    needs_review_count: int


@dataclass(frozen=True)
class ConceptMatch:
    concept_id: str
    confidence: float
    rule_id: str


@dataclass(frozen=True)
class UnitResolution:
    raw_unit: str | None
    currency: str | None
    scale_factor: Decimal | None
    unit_confidence: float


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _normalize_label(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _match_concept(raw_label: str, concept_aliases: dict[str, Any]) -> ConceptMatch | None:
    normalized = _normalize_label(raw_label)
    for concept_id, rule in concept_aliases.get("concepts", {}).items():
        for alias in rule.get("aliases", []) or []:
            if _normalize_label(str(alias)) == normalized:
                return ConceptMatch(
                    concept_id=str(concept_id),
                    confidence=float(rule.get("confidence", 0.0)),
                    rule_id=f"concept_aliases.{concept_id}",
                )
    return None


def _contains_pattern(text: str, pattern: str) -> bool:
    return pattern.lower() in text.lower()


def _resolve_unit(text: str, unit_patterns: dict[str, Any]) -> UnitResolution:
    currency = None
    raw_currency_pattern = None
    for currency_code, patterns in unit_patterns.get("currency_patterns", {}).items():
        for pattern in patterns or []:
            if _contains_pattern(text, str(pattern)):
                currency = str(currency_code)
                raw_currency_pattern = str(pattern)
                break
        if currency is not None:
            break

    scale_factor = None
    raw_scale_pattern = None
    for scale, patterns in unit_patterns.get("scale_patterns", {}).items():
        for pattern in patterns or []:
            if _contains_pattern(text, str(pattern)):
                scale_factor = Decimal(str(scale))
                raw_scale_pattern = str(pattern)
                break
        if scale_factor is not None:
            break

    if (
        raw_currency_pattern is not None
        and raw_scale_pattern is not None
        and raw_currency_pattern.lower() in raw_scale_pattern.lower()
    ):
        raw_unit_parts = [raw_scale_pattern]
    else:
        raw_unit_parts = [
            part for part in [raw_currency_pattern, raw_scale_pattern] if part is not None
        ]
    return UnitResolution(
        raw_unit=" ".join(raw_unit_parts) if raw_unit_parts else None,
        currency=currency,
        scale_factor=scale_factor,
        unit_confidence=0.99 if currency is not None and scale_factor is not None else 0.0,
    )


def _parse_decimal(raw_value: str | None) -> Decimal | None:
    if raw_value is None:
        return None
    cleaned = raw_value.strip().replace(",", "")
    if cleaned in {"", "-", "--"}:
        return None
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if match is None:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _get_run_report(conn: Connection, extraction_run_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        select reports.report_id, reports.market, reports.company_id,
               reports.fiscal_year, reports.report_type
        from extraction_runs
        join reports on reports.report_id = extraction_runs.report_id
        where extraction_runs.extraction_run_id = ?
        """,
        (extraction_run_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown extraction_run_id: {extraction_run_id}")
    return {
        "report_id": str(row[0]),
        "market": str(row[1]),
        "company_id": row[2],
        "fiscal_year": row[3],
        "report_type": row[4],
    }


def _table_context(conn: Connection, report_id: str, raw_table_id: str, page_number: int) -> str:
    parts = []
    page = conn.execute(
        """
        select page_text_sample
        from pdf_pages
        where report_id = ? and page_number = ?
        """,
        (report_id, page_number),
    ).fetchone()
    if page is not None and page[0]:
        parts.append(str(page[0]))

    table = conn.execute(
        "select raw_table_text from raw_tables where raw_table_id = ?",
        (raw_table_id,),
    ).fetchone()
    if table is not None and table[0]:
        parts.append(str(table[0]))

    return "\n".join(parts)


def _cells_by_row(conn: Connection, raw_table_id: str) -> dict[int, dict[int, dict[str, Any]]]:
    rows: dict[int, dict[int, dict[str, Any]]] = {}
    for row in conn.execute(
        """
        select raw_cell_id, row_index, column_index, raw_text, bbox_json, page_number
        from raw_cells
        where raw_table_id = ?
        order by row_index, column_index
        """,
        (raw_table_id,),
    ).fetchall():
        rows.setdefault(int(row[1]), {})[int(row[2])] = {
            "raw_cell_id": str(row[0]),
            "raw_text": row[3],
            "bbox_json": row[4],
            "page_number": int(row[5]),
        }
    return rows


def _header_label(rows: dict[int, dict[int, dict[str, Any]]], column_index: int) -> str | None:
    header = rows.get(0, {}).get(column_index)
    if header is None:
        return None
    return header["raw_text"]


def extract_facts_for_run(
    conn: Connection,
    extraction_run_id: str,
    *,
    rules_root: Path,
) -> FactExtractionSummary:
    report = _get_run_report(conn, extraction_run_id)
    rule_pack = load_market_rule_pack(rules_root, report["market"])

    classified_tables = conn.execute(
        """
        select classified_tables.raw_table_id, classified_tables.table_role,
               classified_tables.statement_scope, raw_tables.page_number,
               raw_tables.extractor_name
        from classified_tables
        join raw_tables on raw_tables.raw_table_id = classified_tables.raw_table_id
        where classified_tables.extraction_run_id = ?
          and classified_tables.table_role = 'statement.balance_sheet'
        order by raw_tables.page_number, raw_tables.table_index_on_page
        """,
        (extraction_run_id,),
    ).fetchall()

    conn.execute(
        "delete from extracted_facts where extraction_run_id = ?",
        (extraction_run_id,),
    )

    facts: list[tuple[object, ...]] = []
    for raw_table_id, table_role, statement_scope, page_number, extractor_name in classified_tables:
        raw_table_id = str(raw_table_id)
        rows = _cells_by_row(conn, raw_table_id)
        unit = _resolve_unit(
            _table_context(conn, report["report_id"], raw_table_id, int(page_number)),
            rule_pack.unit_patterns,
        )

        for row_index, cells in rows.items():
            if row_index == 0:
                continue
            label_cell = cells.get(0)
            value_cell = cells.get(1)
            if label_cell is None:
                continue

            raw_label = label_cell["raw_text"]
            if raw_label is None:
                continue

            concept = _match_concept(str(raw_label), rule_pack.concept_aliases)
            if concept is None:
                continue

            raw_value = value_cell["raw_text"] if value_cell is not None else None
            parsed_decimal = _parse_decimal(raw_value)
            normalized_value = (
                parsed_decimal * unit.scale_factor
                if parsed_decimal is not None and unit.scale_factor is not None
                else None
            )
            fact_status = (
                "normalized"
                if parsed_decimal is not None and unit.unit_confidence >= 0.95
                else "needs_review"
            )
            facts.append(
                (
                    str(uuid.uuid4()),
                    extraction_run_id,
                    report["report_id"],
                    raw_table_id,
                    value_cell["raw_cell_id"] if value_cell is not None else None,
                    "pdf",
                    report["market"],
                    report["company_id"],
                    report["fiscal_year"],
                    report["report_type"],
                    statement_scope,
                    "balance_sheet",
                    table_role,
                    "point_in_time",
                    None,
                    None,
                    None,
                    str(raw_label),
                    concept.concept_id,
                    concept.confidence,
                    concept.rule_id,
                    raw_value,
                    _decimal_text(parsed_decimal),
                    unit.raw_unit,
                    unit.currency,
                    _decimal_text(unit.scale_factor),
                    _decimal_text(normalized_value),
                    unit.unit_confidence,
                    str(raw_label),
                    _header_label(rows, 1),
                    page_number,
                    value_cell["bbox_json"] if value_cell is not None else None,
                    extractor_name,
                    None,
                    fact_status,
                    _utc_now_iso(),
                )
            )

    conn.executemany(
        """
        insert into extracted_facts (
          fact_id, extraction_run_id, report_id, raw_table_id, raw_cell_id,
          source_type, market, company_id, fiscal_year, report_type,
          statement_scope, statement_type, table_role, period_basis,
          period_start, period_end, instant_date, raw_label,
          normalized_concept_id, mapping_confidence, mapping_rule_id, raw_value,
          parsed_decimal, raw_unit, currency, scale_factor, normalized_value,
          unit_confidence, row_label, column_label, page_number, cell_bbox_json,
          extractor_name, extractor_confidence, fact_status, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        facts,
    )
    conn.commit()

    needs_review = sum(1 for fact in facts if fact[-2] == "needs_review")
    return FactExtractionSummary(
        extraction_run_id=extraction_run_id,
        fact_count=len(facts),
        needs_review_count=needs_review,
    )
