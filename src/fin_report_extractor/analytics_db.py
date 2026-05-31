from __future__ import annotations

from pathlib import Path

import duckdb


def initialize_analytics_db(path: str | Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table if not exists trusted_facts (
              trusted_version_id varchar,
              fact_id varchar,
              report_id varchar,
              extraction_run_id varchar,
              company_id varchar,
              company_name varchar,
              market varchar,
              fiscal_year integer,
              report_type varchar,
              statement_scope varchar,
              statement_type varchar,
              table_role varchar,
              period_basis varchar,
              period_end date,
              instant_date date,
              effective_concept_id varchar,
              raw_label varchar,
              effective_value decimal(38, 6),
              effective_unit varchar,
              currency varchar,
              source_page integer,
              trusted_status varchar
            )
            """
        )
    finally:
        conn.close()
