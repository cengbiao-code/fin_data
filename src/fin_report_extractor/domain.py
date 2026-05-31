from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


ValidationStatus = Literal[
    "verified",
    "verified_with_rounding",
    "failed",
    "blocked_unit_unknown",
    "blocked_extractor_conflict",
    "requires_manual_review",
    "manually_confirmed",
]


@dataclass(frozen=True)
class FactRef:
    fact_id: str
    concept_id: str
    value: Decimal | None
    raw_value: str | None
    currency: str | None
    scale_factor: Decimal | None
    unit_confidence: float
    page_number: int
    table_role: str
    row_label: str | None
    column_label: str | None
    cell_bbox_json: str | None


@dataclass(frozen=True)
class RuleTolerance:
    absolute_tolerance: Decimal
    relative_tolerance: Decimal


@dataclass(frozen=True)
class ValidationResult:
    rule_id: str
    rule_name: str
    severity: Literal["error", "warning"]
    status: ValidationStatus
    lhs_value: Decimal | None
    rhs_value: Decimal | None
    difference_value: Decimal | None
    involved_fact_ids: list[str]
    message: str
