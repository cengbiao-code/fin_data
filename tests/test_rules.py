from pathlib import Path

from fin_report_extractor import __version__
from fin_report_extractor.rules import load_market_rule_pack


def test_package_imports():
    assert __version__ == "0.1.0"


def test_load_a_share_rule_pack():
    rule_pack = load_market_rule_pack(Path("rules"), "a_share")

    assert rule_pack.market == "a_share"
    assert "statement.balance_sheet" in rule_pack.table_titles["statement_titles"]
    assert "total_assets" in rule_pack.concept_aliases["concepts"]
    assert "CNY" in rule_pack.unit_patterns["currency_patterns"]
    assert "cumulative" in rule_pack.period_patterns["period_patterns"]
    assert "note.revenue_by_product" in rule_pack.note_roles["note_roles"]
    assert "tolerance" in rule_pack.validation_overrides
    assert rule_pack.version_hash


def test_missing_required_rule_file_fails_clearly(tmp_path):
    market_dir = tmp_path / "rules" / "a_share"
    market_dir.mkdir(parents=True)

    try:
        load_market_rule_pack(tmp_path / "rules", "a_share")
    except FileNotFoundError as exc:
        assert "Missing rule files" in str(exc)
        assert "table_titles.yml" in str(exc)
    else:
        raise AssertionError("Expected missing rule files to fail clearly")
