from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fin_report_extractor.domain import (
    FactRef,
    RuleTolerance,
    ValidationResult,
    ValidationStatus,
)


BALANCE_SHEET_RULE_ID = "balance_sheet.assets_equal_liabilities_plus_equity"
BALANCE_SHEET_RULE_NAME = "资产总计 = 负债合计 + 权益合计"
MINIMUM_UNIT_CONFIDENCE = 0.95


def validate_assets_equal_liabilities_plus_equity(
    facts: dict[str, FactRef],
    tolerance: RuleTolerance,
) -> ValidationResult:
    assets = facts.get("total_assets")
    liabilities = facts.get("total_liabilities")
    equity = facts.get("total_equity")
    required_facts = [assets, liabilities, equity]
    involved = [
        fact.fact_id
        for fact in required_facts
        if fact is not None
    ]

    if assets is None or liabilities is None or equity is None:
        return _result(
            status="requires_manual_review",
            involved_fact_ids=involved,
            message="缺少资产总计、负债合计或权益合计，无法自动校验。",
        )

    if any(_has_unknown_unit(fact) for fact in required_facts):
        return _result(
            status="blocked_unit_unknown",
            involved_fact_ids=involved,
            message="相关数值存在单位不明确，不能进入可信库。",
        )

    if assets.value is None or liabilities.value is None or equity.value is None:
        return _result(
            status="requires_manual_review",
            involved_fact_ids=involved,
            message="资产总计、负债合计或权益合计缺少数值，无法自动校验。",
        )

    lhs = assets.value
    rhs = liabilities.value + equity.value
    difference = lhs - rhs

    if difference == 0:
        status = "verified"
    elif _within_tolerance(difference, lhs, tolerance):
        status = "verified_with_rounding"
    else:
        status = "failed"

    return _result(
        status=status,
        lhs_value=lhs,
        rhs_value=rhs,
        difference_value=difference,
        involved_fact_ids=involved,
        message=f"资产总计 {lhs}，负债+权益 {rhs}，差异 {difference}。",
    )


def _has_unknown_unit(fact: FactRef | None) -> bool:
    return (
        fact is None
        or fact.scale_factor is None
        or fact.unit_confidence < MINIMUM_UNIT_CONFIDENCE
    )


def _within_tolerance(
    difference: Decimal,
    lhs: Decimal,
    tolerance: RuleTolerance,
) -> bool:
    absolute_difference = abs(difference)
    if absolute_difference <= tolerance.absolute_tolerance:
        return True

    if lhs == 0:
        return False

    try:
        return abs(difference / lhs) <= tolerance.relative_tolerance
    except (InvalidOperation, ZeroDivisionError):
        return False


def _result(
    *,
    status: ValidationStatus,
    involved_fact_ids: list[str],
    message: str,
    lhs_value: Decimal | None = None,
    rhs_value: Decimal | None = None,
    difference_value: Decimal | None = None,
) -> ValidationResult:
    return ValidationResult(
        rule_id=BALANCE_SHEET_RULE_ID,
        rule_name=BALANCE_SHEET_RULE_NAME,
        severity="error",
        status=status,
        lhs_value=lhs_value,
        rhs_value=rhs_value,
        difference_value=difference_value,
        involved_fact_ids=involved_fact_ids,
        message=message,
    )
