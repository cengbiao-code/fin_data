from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Connection

import duckdb


TRUSTED_STATUSES = frozenset(
    {
        "verified",
        "verified_with_rounding",
        "manually_confirmed",
    }
)


def is_trusted_status(status: str) -> bool:
    return status in TRUSTED_STATUSES


def publish_trusted_version(
    audit_conn: Connection,
    analytics_db_path: str | Path,
    extraction_run_id: str,
    *,
    notes: str | None = None,
) -> str:
    """Publish verified facts from SQLite audit DB to DuckDB analytics DB.

    1. Query SQLite ``extracted_facts`` for publishable facts (those with a
       ``normalized_concept_id`` and ``unit_confidence >= 0.95``) in the
       given extraction run.
    2. Write matching facts into the DuckDB ``trusted_facts`` table.
    3. Create or replace wide-table pivot views for BS, IS, and CF.
    4. Record a ``trusted_versions`` entry in SQLite.
    5. Return the ``trusted_version_id``.

    Raises ``ValueError`` if no publishable facts are found.
    """
    report_id = _get_report_id(audit_conn, extraction_run_id)
    facts = _publishable_facts(audit_conn, extraction_run_id)
    if not facts:
        raise ValueError(
            f"No publishable facts found for extraction run {extraction_run_id}"
        )

    trusted_version_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    # Build rows for DuckDB trusted_facts
    duck_rows = [
        (
            trusted_version_id,
            fact["fact_id"],
            report_id,
            extraction_run_id,
            fact["company_id"],
            fact["company_name"],
            fact["market"],
            fact["fiscal_year"],
            fact["report_type"],
            fact["statement_scope"],
            fact["statement_type"],
            fact["table_role"],
            fact["period_basis"],
            fact["period_end"],
            fact["instant_date"],
            fact["normalized_concept_id"],
            fact["raw_label"],
            fact["effective_value"],
            fact["raw_unit"],
            fact["currency"],
            fact["page_number"],
            "verified",
        )
        for fact in facts
    ]

    analytics_conn = duckdb.connect(str(analytics_db_path))
    try:
        analytics_conn.executemany(
            """
            insert into trusted_facts (
              trusted_version_id, fact_id, report_id, extraction_run_id,
              company_id, company_name, market, fiscal_year, report_type,
              statement_scope, statement_type, table_role, period_basis,
              period_end, instant_date, effective_concept_id, raw_label,
              effective_value, effective_unit, currency, source_page,
              trusted_status
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            duck_rows,
        )
        _create_wide_views(analytics_conn)
    finally:
        analytics_conn.close()

    # Record trusted version in SQLite
    audit_conn.execute(
        """
        insert into trusted_versions (
          trusted_version_id, report_id, extraction_run_id, scope, scope_key,
          status, published_at, notes
        ) values (?, ?, ?, 'report', NULL, 'active', ?, ?)
        """,
        (
            trusted_version_id,
            report_id,
            extraction_run_id,
            now_iso,
            notes,
        ),
    )
    audit_conn.commit()

    return trusted_version_id


def _get_report_id(conn: Connection, extraction_run_id: str) -> str:
    row = conn.execute(
        "select report_id from extraction_runs where extraction_run_id = ?",
        (extraction_run_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Extraction run not found: {extraction_run_id}")
    return str(row[0])


def _publishable_facts(conn: Connection, extraction_run_id: str) -> list[dict]:
    """Fetch facts that are ready for trusted publishing.

    A fact is publishable when it has a mapped concept (normalized_concept_id)
    and a high-confidence unit (unit_confidence >= 0.95). Both fact statuses
    ``'normalized'`` and ``'validated'`` are accepted — validated facts have
    passed validation checks, while normalized facts have a concept mapping
    but no validation run yet.
    """
    rows = conn.execute(
        """
        select
          ef.fact_id,
          ef.report_id,
          ef.extraction_run_id,
          r.company_id,
          r.company_name,
          r.market,
          r.fiscal_year,
          r.report_type,
          ef.statement_scope,
          ef.statement_type,
          ef.table_role,
          ef.period_basis,
          ef.period_end,
          ef.instant_date,
          ef.normalized_concept_id,
          ef.raw_label,
          cast(ef.normalized_value as decimal(38, 6)) as effective_value,
          ef.raw_unit,
          ef.currency,
          ef.page_number,
          ef.unit_confidence,
          ef.fact_status
        from extracted_facts ef
        join reports r on r.report_id = ef.report_id
        where ef.extraction_run_id = ?
          and ef.normalized_concept_id is not null
          and ef.normalized_value is not null
          and ef.unit_confidence >= 0.95
          and ef.fact_status in ('normalized', 'validated')
        """,
        (extraction_run_id,),
    )
    columns = [desc[0] for desc in rows.description]
    return [dict(zip(columns, row)) for row in rows]


def _create_wide_views(conn: duckdb.DuckDBPyConnection) -> None:
    """Create or replace wide-table pivot views for BS, IS, and CF.

    Each view pivots the long-format ``trusted_facts`` table into one row
    per (company, period) with selected concept columns.
    """
    views = [
        (
            "statement_wide_balance_sheet",
            "balance_sheet",
            ["total_assets", "total_liabilities", "total_equity"],
        ),
        (
            "statement_wide_income_statement",
            "income_statement",
            ["revenue", "net_profit", "earnings_per_share"],
        ),
        (
            "statement_wide_cash_flow",
            "cash_flow",
            [
                "net_cash_flow_from_operating",
                "net_cash_flow_from_investing",
                "net_cash_flow_from_financing",
                "cash_and_cash_equivalents",
            ],
        ),
    ]

    for view_name, statement_type, concepts in views:
        select_exprs = []
        for concept in concepts:
            select_exprs.append(
                f"max(case when effective_concept_id = '{concept}' "
                f"then effective_value end) as {concept}"
            )
        select_clause = ",\n              ".join(select_exprs)

        conn.execute(f"""
            create or replace view {view_name} as
            select
              trusted_version_id,
              report_id,
              company_id,
              company_name,
              market,
              fiscal_year,
              report_type,
              statement_scope,
              period_end,
              {select_clause}
            from trusted_facts
            where statement_type = '{statement_type}'
            group by trusted_version_id, report_id, company_id, company_name,
                     market, fiscal_year, report_type, statement_scope, period_end
        """)
