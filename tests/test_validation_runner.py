from pathlib import Path

from fin_report_extractor.fact_extractor import extract_facts_for_run
from fin_report_extractor.validation_runner import validate_extraction_run
from tests.test_fact_extractor import _setup_classified_balance_sheet


def test_validate_extraction_run_writes_balance_sheet_result(tmp_path):
    conn, _report_id, run_id = _setup_classified_balance_sheet(tmp_path)
    try:
        extract_facts_for_run(conn, run_id, rules_root=Path("rules"))

        summary = validate_extraction_run(conn, run_id, rules_root=Path("rules"))

        assert summary.result_count == 1
        assert summary.failed_count == 0

        validation_run = conn.execute(
            """
            select extraction_run_id, status, rule_pack_version, finished_at
            from validation_runs
            where validation_run_id = ?
            """,
            (summary.validation_run_id,),
        ).fetchone()
        assert validation_run[0] == run_id
        assert validation_run[1] == "succeeded"
        assert validation_run[2]
        assert validation_run[3] is not None

        result = conn.execute(
            """
            select rule_id, status, lhs_value, rhs_value, difference_value,
                   involved_fact_ids_json
            from validation_results
            where validation_run_id = ?
            """,
            (summary.validation_run_id,),
        ).fetchone()

        assert result[0] == "balance_sheet.assets_equal_liabilities_plus_equity"
        assert result[1] == "verified"
        assert result[2] == "100000"
        assert result[3] == "100000"
        assert result[4] == "0"
        assert "total_assets" not in result[5]

    finally:
        conn.close()


def test_validate_run_cli_writes_validation_result(tmp_path, capsys):
    from fin_report_extractor.cli import main

    conn, _report_id, run_id = _setup_classified_balance_sheet(tmp_path)
    try:
        extract_facts_for_run(conn, run_id, rules_root=Path("rules"))
    finally:
        conn.close()

    main(
        [
            "validate-run",
            run_id,
            "--audit-db",
            str(tmp_path / "audit.sqlite"),
            "--rules-root",
            "rules",
        ]
    )

    output = capsys.readouterr().out
    assert f"extraction_run_id={run_id}" in output
    assert "results=1" in output
    assert "failed=0" in output
