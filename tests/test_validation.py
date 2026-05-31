from decimal import Decimal

from fin_report_extractor.domain import FactRef, RuleTolerance, ValidationResult


def test_fact_ref_keeps_decimal_value():
    fact = FactRef(
        fact_id="fact-1",
        concept_id="total_assets",
        value=Decimal("100"),
        raw_value="100",
        currency="CNY",
        scale_factor=Decimal("10000"),
        unit_confidence=0.99,
        page_number=12,
        table_role="statement.balance_sheet",
        row_label="资产总计",
        column_label="期末余额",
        cell_bbox_json="[1,2,3,4]",
    )

    assert fact.value == Decimal("100")
    assert fact.concept_id == "total_assets"


def test_rule_tolerance_defaults_are_explicit():
    tolerance = RuleTolerance(
        absolute_tolerance=Decimal("2"),
        relative_tolerance=Decimal("0.0001"),
    )

    assert tolerance.absolute_tolerance == Decimal("2")
    assert tolerance.relative_tolerance == Decimal("0.0001")


def test_validation_result_tracks_rule_status_and_facts():
    result = ValidationResult(
        rule_id="balance_sheet.assets_equal_liabilities_plus_equity",
        rule_name="Assets equal liabilities plus equity",
        severity="error",
        status="requires_manual_review",
        lhs_value=Decimal("100"),
        rhs_value=Decimal("99"),
        difference_value=Decimal("1"),
        involved_fact_ids=["fact-1", "fact-2", "fact-3"],
        message="Needs manual review.",
    )

    assert result.status == "requires_manual_review"
    assert result.involved_fact_ids == ["fact-1", "fact-2", "fact-3"]
