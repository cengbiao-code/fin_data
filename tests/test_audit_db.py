import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db


@contextmanager
def _db_path() -> Iterator[Path]:
    with TemporaryDirectory() as temp_dir:
        yield Path(temp_dir) / "audit.sqlite"


def test_connect_audit_db_opens_sqlite_connection():
    with _db_path() as db_path:
        conn = connect_audit_db(db_path)

        try:
            conn.execute("select 1").fetchone()
        finally:
            conn.close()


def test_initialize_audit_db_creates_core_tables():
    with _db_path() as db_path:
        conn = connect_audit_db(db_path)

        try:
            initialize_audit_db(conn)

            table_names = {
                row[0]
                for row in conn.execute(
                    "select name from sqlite_master where type = 'table'"
                ).fetchall()
            }

            assert {
                "reports",
                "extraction_runs",
                "pdf_pages",
                "raw_tables",
                "raw_cells",
                "classified_tables",
                "extracted_facts",
                "validation_runs",
                "validation_results",
                "review_exports",
                "correction_batches",
                "corrections",
                "trusted_versions",
                "rule_pack_versions",
            }.issubset(table_names)
        finally:
            conn.close()


def test_reports_file_hash_is_unique():
    with _db_path() as db_path:
        conn = connect_audit_db(db_path)
        try:
            initialize_audit_db(conn)

            sql = """
            insert into reports (
              report_id, file_sha256, original_filename, stored_pdf_path,
              market, source_type, is_text_pdf, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """
            conn.execute(
                sql,
                (
                    "report-1",
                    "same-sha",
                    "first.pdf",
                    "data/raw/first.pdf",
                    "a_share",
                    "pdf",
                    1,
                    "2026-05-31T00:00:00Z",
                ),
            )

            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    sql,
                    (
                        "report-2",
                        "same-sha",
                        "second.pdf",
                        "data/raw/second.pdf",
                        "a_share",
                        "pdf",
                        1,
                        "2026-05-31T00:00:01Z",
                    ),
                )
        finally:
            conn.close()


def test_only_one_active_trusted_version_per_report_scope_and_key():
    with _db_path() as db_path:
        conn = connect_audit_db(db_path)
        try:
            initialize_audit_db(conn)
            conn.execute(
                """
                insert into reports (
                  report_id, file_sha256, original_filename, stored_pdf_path,
                  market, source_type, is_text_pdf, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "report-1",
                    "sha-1",
                    "report.pdf",
                    "data/raw/report.pdf",
                    "a_share",
                    "pdf",
                    1,
                    "2026-05-31T00:00:00Z",
                ),
            )
            conn.execute(
                """
                insert into extraction_runs (
                  extraction_run_id, report_id, run_started_at, status,
                  pipeline_version, rule_pack_version, extractor_versions_json
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "run-1",
                    "report-1",
                    "2026-05-31T00:00:00Z",
                    "succeeded",
                    "0.1.0",
                    "rules-1",
                    "{}",
                ),
            )
            conn.execute(
                """
                insert into extraction_runs (
                  extraction_run_id, report_id, run_started_at, status,
                  pipeline_version, rule_pack_version, extractor_versions_json
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "run-2",
                    "report-1",
                    "2026-05-31T00:01:00Z",
                    "succeeded",
                    "0.1.0",
                    "rules-1",
                    "{}",
                ),
            )
            sql = """
            insert into trusted_versions (
              trusted_version_id, report_id, extraction_run_id, scope, scope_key,
              status, published_at
            ) values (?, ?, ?, ?, ?, ?, ?)
            """
            conn.execute(
                sql,
                (
                    "trusted-1",
                    "report-1",
                    "run-1",
                    "statement",
                    "statement.balance_sheet",
                    "active",
                    "2026-05-31T00:02:00Z",
                ),
            )
            conn.execute(
                sql,
                (
                    "trusted-2",
                    "report-1",
                    "run-2",
                    "statement",
                    "statement.balance_sheet",
                    "inactive",
                    "2026-05-31T00:03:00Z",
                ),
            )

            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    sql,
                    (
                        "trusted-3",
                        "report-1",
                        "run-2",
                        "statement",
                        "statement.balance_sheet",
                        "active",
                        "2026-05-31T00:04:00Z",
                    ),
                )
        finally:
            conn.close()
