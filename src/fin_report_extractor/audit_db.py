from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_audit_db(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("pragma foreign_keys = on")
    return conn


def initialize_audit_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists reports (
          report_id text primary key,
          file_sha256 text not null unique,
          original_filename text not null,
          stored_pdf_path text not null,
          market text not null,
          company_id text,
          company_name text,
          fiscal_year integer,
          report_type text,
          source_type text not null,
          page_count integer,
          is_text_pdf integer not null,
          unsupported_reason text,
          created_at text not null
        );

        create index if not exists idx_reports_company_period
        on reports (market, company_id, fiscal_year, report_type);

        create table if not exists extraction_runs (
          extraction_run_id text primary key,
          report_id text not null references reports(report_id),
          run_started_at text not null,
          run_finished_at text,
          status text not null,
          pipeline_version text not null,
          rule_pack_version text not null,
          extractor_versions_json text not null,
          error_message text
        );

        create index if not exists idx_extraction_runs_report
        on extraction_runs (report_id);

        create index if not exists idx_extraction_runs_report_started
        on extraction_runs (report_id, run_started_at);

        create table if not exists pdf_pages (
          page_id text primary key,
          report_id text not null references reports(report_id),
          page_number integer not null,
          width real,
          height real,
          text_char_count integer not null,
          text_density real,
          has_statement_keywords integer not null,
          page_text_sample text,
          unique (report_id, page_number)
        );

        create table if not exists raw_tables (
          raw_table_id text primary key,
          extraction_run_id text not null references extraction_runs(extraction_run_id),
          report_id text not null references reports(report_id),
          extractor_name text not null,
          extractor_table_id text,
          page_number integer not null,
          table_index_on_page integer not null,
          bbox_json text,
          row_count integer,
          column_count integer,
          quality_json text,
          raw_table_text text,
          created_at text not null
        );

        create index if not exists idx_raw_tables_run_page
        on raw_tables (extraction_run_id, page_number);

        create index if not exists idx_raw_tables_report_page
        on raw_tables (report_id, page_number);

        create table if not exists raw_cells (
          raw_cell_id text primary key,
          raw_table_id text not null references raw_tables(raw_table_id),
          extraction_run_id text not null references extraction_runs(extraction_run_id),
          report_id text not null references reports(report_id),
          row_index integer not null,
          column_index integer not null,
          raw_text text,
          normalized_text text,
          bbox_json text,
          page_number integer not null,
          is_header_candidate integer not null,
          created_at text not null
        );

        create table if not exists classified_tables (
          classified_table_id text primary key,
          raw_table_id text not null references raw_tables(raw_table_id),
          extraction_run_id text not null references extraction_runs(extraction_run_id),
          table_role text not null,
          statement_scope text not null,
          classification_confidence real not null,
          classification_rule_id text,
          requires_review integer not null,
          created_at text not null
        );

        create table if not exists extracted_facts (
          fact_id text primary key,
          extraction_run_id text not null references extraction_runs(extraction_run_id),
          report_id text not null references reports(report_id),
          raw_table_id text not null references raw_tables(raw_table_id),
          raw_cell_id text references raw_cells(raw_cell_id),
          source_type text not null,
          market text not null,
          company_id text,
          fiscal_year integer,
          report_type text,
          statement_scope text not null,
          statement_type text,
          table_role text not null,
          period_basis text not null,
          period_start text,
          period_end text,
          instant_date text,
          raw_label text not null,
          normalized_concept_id text,
          mapping_confidence real not null,
          mapping_rule_id text,
          raw_value text,
          parsed_decimal text,
          raw_unit text,
          currency text,
          scale_factor text,
          normalized_value text,
          unit_confidence real not null,
          row_label text,
          column_label text,
          page_number integer not null,
          cell_bbox_json text,
          extractor_name text not null,
          extractor_confidence real,
          fact_status text not null,
          created_at text not null
        );

        create index if not exists idx_extracted_facts_report_run
        on extracted_facts (report_id, extraction_run_id);

        create index if not exists idx_extracted_facts_concept_period
        on extracted_facts (normalized_concept_id, period_end);

        create index if not exists idx_extracted_facts_role_scope
        on extracted_facts (table_role, statement_scope);

        create table if not exists validation_runs (
          validation_run_id text primary key,
          extraction_run_id text not null references extraction_runs(extraction_run_id),
          rule_pack_version text not null,
          started_at text not null,
          finished_at text,
          status text not null
        );

        create table if not exists validation_results (
          validation_result_id text primary key,
          validation_run_id text not null references validation_runs(validation_run_id),
          extraction_run_id text not null references extraction_runs(extraction_run_id),
          rule_id text not null,
          rule_name text not null,
          severity text not null,
          status text not null,
          lhs_value text,
          rhs_value text,
          difference_value text,
          absolute_tolerance text,
          relative_tolerance text,
          involved_fact_ids_json text not null,
          message text not null,
          created_at text not null
        );

        create table if not exists review_exports (
          review_export_id text primary key,
          report_id text not null references reports(report_id),
          extraction_run_id text not null references extraction_runs(extraction_run_id),
          validation_run_id text references validation_runs(validation_run_id),
          workbook_path text not null,
          html_summary_path text,
          status text not null,
          created_at text not null
        );

        create table if not exists correction_batches (
          correction_batch_id text primary key,
          review_export_id text not null references review_exports(review_export_id),
          report_id text not null references reports(report_id),
          extraction_run_id text not null references extraction_runs(extraction_run_id),
          imported_workbook_path text not null,
          operator text,
          imported_at text not null,
          status text not null,
          error_message text
        );

        create table if not exists corrections (
          correction_id text primary key,
          correction_batch_id text not null references correction_batches(correction_batch_id),
          fact_id text not null references extracted_facts(fact_id),
          field_name text not null,
          old_value text,
          new_value text,
          correction_reason text not null,
          created_at text not null
        );

        create table if not exists trusted_versions (
          trusted_version_id text primary key,
          report_id text not null references reports(report_id),
          extraction_run_id text not null references extraction_runs(extraction_run_id),
          scope text not null,
          scope_key text,
          status text not null,
          published_at text not null,
          published_by text,
          notes text
        );

        create unique index if not exists idx_one_active_trusted_version
        on trusted_versions (report_id, scope, coalesce(scope_key, ''))
        where status = 'active';

        create table if not exists rule_pack_versions (
          rule_pack_version text primary key,
          market text not null,
          rules_path text not null,
          created_at text not null
        );
        """
    )
    conn.commit()
