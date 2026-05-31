from decimal import Decimal

from fin_report_extractor.domain import FactRef, RuleTolerance, ValidationResult
from fin_report_extractor.validation import (
    validate_assets_equal_liabilities_plus_equity,
)


def _fact(
    concept_id: str,
    value: str | None,
    fact_id: str,
    *,
    scale_factor: Decimal | None = Decimal("1"),
    unit_confidence: float = 0.99,
) -> FactRef:
    return FactRef(
        fact_id=fact_id,
        concept_id=concept_id,
        value=Decimal(value) if value is not None else None,
        raw_value=value,
        currency="CNY",
        scale_factor=scale_factor,
        unit_confidence=unit_confidence,
        page_number=1,
        table_role="statement.balance_sheet",
        row_label=concept_id,
        column_label="期末余额",
        cell_bbox_json="[0,0,1,1]",
    )


def _tolerance() -> RuleTolerance:
    return RuleTolerance(
        absolute_tolerance=Decimal("2"),
        relative_tolerance=Decimal("0.0001"),
    )


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


def test_assets_equal_liabilities_plus_equity_verified():
    result = validate_assets_equal_liabilities_plus_equity(
        {
            "total_assets": _fact("total_assets", "100", "fact-assets"),
            "total_liabilities": _fact(
                "total_liabilities",
                "60",
                "fact-liabilities",
            ),
            "total_equity": _fact("total_equity", "40", "fact-equity"),
        },
        _tolerance(),
    )

    assert result.status == "verified"
    assert result.lhs_value == Decimal("100")
    assert result.rhs_value == Decimal("100")
    assert result.difference_value == Decimal("0")
    assert result.involved_fact_ids == [
        "fact-assets",
        "fact-liabilities",
        "fact-equity",
    ]


def test_assets_equal_liabilities_plus_equity_verified_with_rounding():
    result = validate_assets_equal_liabilities_plus_equity(
        {
            "total_assets": _fact("total_assets", "100", "fact-assets"),
            "total_liabilities": _fact(
                "total_liabilities",
                "59",
                "fact-liabilities",
            ),
            "total_equity": _fact("total_equity", "40", "fact-equity"),
        },
        _tolerance(),
    )

    assert result.status == "verified_with_rounding"
    assert result.difference_value == Decimal("1")


def test_assets_equal_liabilities_plus_equity_failed():
    result = validate_assets_equal_liabilities_plus_equity(
        {
            "total_assets": _fact("total_assets", "100", "fact-assets"),
            "total_liabilities": _fact(
                "total_liabilities",
                "50",
                "fact-liabilities",
            ),
            "total_equity": _fact("total_equity", "40", "fact-equity"),
        },
        _tolerance(),
    )

    assert result.status == "failed"
    assert result.difference_value == Decimal("10")


def test_assets_equal_liabilities_plus_equity_blocks_unknown_unit():
    result = validate_assets_equal_liabilities_plus_equity(
        {
            "total_assets": _fact("total_assets", "100", "fact-assets"),
            "total_liabilities": _fact(
                "total_liabilities",
                "60",
                "fact-liabilities",
                scale_factor=None,
            ),
            "total_equity": _fact("total_equity", "40", "fact-equity"),
        },
        _tolerance(),
    )

    assert result.status == "blocked_unit_unknown"
    assert result.lhs_value is None
    assert result.rhs_value is None
    assert result.difference_value is None


def test_assets_equal_liabilities_plus_equity_requires_manual_review_when_missing():
    result = validate_assets_equal_liabilities_plus_equity(
        {
            "total_assets": _fact("total_assets", "100", "fact-assets"),
            "total_liabilities": _fact(
                "total_liabilities",
                "60",
                "fact-liabilities",
            ),
        },
        _tolerance(),
    )

    assert result.status == "requires_manual_review"
    assert result.involved_fact_ids == ["fact-assets", "fact-liabilities"]


def test_assets_equal_liabilities_plus_equity_does_not_modify_facts():
    facts = {
        "total_assets": _fact("total_assets", "100", "fact-assets"),
        "total_liabilities": _fact(
            "total_liabilities",
            "59",
            "fact-liabilities",
        ),
        "total_equity": _fact("total_equity", "40", "fact-equity"),
    }
    before = dict(facts)

    validate_assets_equal_liabilities_plus_equity(facts, _tolerance())

    assert facts == before
