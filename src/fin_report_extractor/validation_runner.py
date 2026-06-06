from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from sqlite3 import Connection

from fin_report_extractor.domain import FactRef, RuleTolerance
from fin_report_extractor.rules import load_market_rule_pack
from fin_report_extractor.validation import validate_assets_equal_liabilities_plus_equity


@dataclass(frozen=True)
class ValidationRunSummary:
    validation_run_id: str
    extraction_run_id: str
    result_count: int
    failed_count: int


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _get_run_market(conn: Connection, extraction_run_id: str) -> str:
    row = conn.execute(
        """
        select reports.market
        from extraction_runs
        join reports on reports.report_id = extraction_runs.report_id
        where extraction_runs.extraction_run_id = ?
        """,
        (extraction_run_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown extraction_run_id: {extraction_run_id}")
    return str(row[0])


def _tolerance(validation_overrides: dict[str, object]) -> RuleTolerance:
    tolerance = validation_overrides.get("tolerance", {})
    if not isinstance(tolerance, dict):
        tolerance = {}
    return RuleTolerance(
        absolute_tolerance=Decimal(
            str(tolerance.get("absolute_tolerance_display_units", "2"))
        ),
        relative_tolerance=Decimal(str(tolerance.get("relative_tolerance", "0.0001"))),
    )


def _balance_sheet_facts(conn: Connection, extraction_run_id: str) -> dict[str, FactRef]:
    facts: dict[str, FactRef] = {}
    for row in conn.execute(
        """
        select fact_id, normalized_concept_id, normalized_value, raw_value,
               currency, scale_factor, unit_confidence, page_number, table_role,
               row_label, column_label, cell_bbox_json
        from extracted_facts
        where extraction_run_id = ?
          and table_role = 'statement.balance_sheet'
          and normalized_concept_id is not null
        """,
        (extraction_run_id,),
    ).fetchall():
        concept_id = str(row[1])
        facts[concept_id] = FactRef(
            fact_id=str(row[0]),
            concept_id=concept_id,
            value=Decimal(str(row[2])) if row[2] is not None else None,
            raw_value=row[3],
            currency=row[4],
            scale_factor=Decimal(str(row[5])) if row[5] is not None else None,
            unit_confidence=float(row[6]),
            page_number=int(row[7]),
            table_role=str(row[8]),
            row_label=row[9],
            column_label=row[10],
            cell_bbox_json=row[11],
        )
    return facts


def validate_extraction_run(
    conn: Connection,
    extraction_run_id: str,
    *,
    rules_root: Path,
) -> ValidationRunSummary:
    market = _get_run_market(conn, extraction_run_id)
    rule_pack = load_market_rule_pack(rules_root, market)
    validation_run_id = str(uuid.uuid4())
    started_at = _utc_now_iso()

    conn.execute(
        """
        insert into validation_runs (
          validation_run_id, extraction_run_id, rule_pack_version, started_at,
          status
        ) values (?, ?, ?, ?, ?)
        """,
        (
            validation_run_id,
            extraction_run_id,
            rule_pack.version_hash,
            started_at,
            "running",
        ),
    )

    result = validate_assets_equal_liabilities_plus_equity(
        _balance_sheet_facts(conn, extraction_run_id),
        _tolerance(rule_pack.validation_overrides),
    )
    conn.execute(
        """
        insert into validation_results (
          validation_result_id, validation_run_id, extraction_run_id, rule_id,
          rule_name, severity, status, lhs_value, rhs_value, difference_value,
          absolute_tolerance, relative_tolerance, involved_fact_ids_json,
          message, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            validation_run_id,
            extraction_run_id,
            result.rule_id,
            result.rule_name,
            result.severity,
            result.status,
            _decimal_text(result.lhs_value),
            _decimal_text(result.rhs_value),
            _decimal_text(result.difference_value),
            _decimal_text(_tolerance(rule_pack.validation_overrides).absolute_tolerance),
            _decimal_text(_tolerance(rule_pack.validation_overrides).relative_tolerance),
            json.dumps(result.involved_fact_ids, ensure_ascii=False),
            result.message,
            _utc_now_iso(),
        ),
    )
    conn.execute(
        """
        update validation_runs
        set status = ?, finished_at = ?
        where validation_run_id = ?
        """,
        ("succeeded", _utc_now_iso(), validation_run_id),
    )
    conn.commit()

    failed_count = 1 if result.status in {"failed", "blocked_unit_unknown"} else 0
    return ValidationRunSummary(
        validation_run_id=validation_run_id,
        extraction_run_id=extraction_run_id,
        result_count=1,
        failed_count=failed_count,
    )
