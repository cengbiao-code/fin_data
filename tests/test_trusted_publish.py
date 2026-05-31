import duckdb

from fin_report_extractor.analytics_db import initialize_analytics_db
from fin_report_extractor.trusted_publish import is_trusted_status


def test_initialize_analytics_db_creates_trusted_facts_table(tmp_path):
    db_path = tmp_path / "analytics.duckdb"

    initialize_analytics_db(db_path)

    assert db_path.exists()
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
    finally:
        conn.close()

    assert "trusted_facts" in tables


def test_is_trusted_status_only_accepts_publishable_statuses():
    trusted_statuses = [
        "verified",
        "verified_with_rounding",
        "manually_confirmed",
    ]
    untrusted_statuses = [
        "raw",
        "normalized",
        "validated",
        "failed",
        "blocked_unit_unknown",
        "blocked_extractor_conflict",
        "requires_manual_review",
        "active",
    ]

    assert all(is_trusted_status(status) for status in trusted_statuses)
    assert not any(is_trusted_status(status) for status in untrusted_statuses)
