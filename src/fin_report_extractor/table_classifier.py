from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection
from typing import Any

from fin_report_extractor.rules import load_market_rule_pack


@dataclass(frozen=True)
class TableClassificationSummary:
    extraction_run_id: str
    classified_count: int
    review_required_count: int


@dataclass(frozen=True)
class TableClassification:
    raw_table_id: str
    table_role: str
    statement_scope: str
    confidence: float
    rule_id: str | None
    requires_review: bool


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _get_run_context(conn: Connection, extraction_run_id: str) -> tuple[str, str]:
    row = conn.execute(
        """
        select extraction_runs.report_id, reports.market
        from extraction_runs
        join reports on reports.report_id = extraction_runs.report_id
        where extraction_runs.extraction_run_id = ?
        """,
        (extraction_run_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown extraction_run_id: {extraction_run_id}")
    return str(row[0]), str(row[1])


def _page_text_sample(
    conn: Connection,
    report_id: str,
    page_number: int,
) -> str | None:
    row = conn.execute(
        """
        select page_text_sample
        from pdf_pages
        where report_id = ? and page_number = ?
        """,
        (report_id, page_number),
    ).fetchone()
    if row is None:
        return None
    return row[0]


def _cell_text(conn: Connection, raw_table_id: str) -> str:
    return "\n".join(
        str(row[0])
        for row in conn.execute(
            """
            select raw_text
            from raw_cells
            where raw_table_id = ? and raw_text is not null
            order by row_index, column_index
            """,
            (raw_table_id,),
        ).fetchall()
    )


def _local_table_text(conn: Connection, raw_table_id: str, raw_table_text: str | None) -> str:
    return "\n".join(part for part in [raw_table_text, _cell_text(conn, raw_table_id)] if part)


def _contains_keyword(text: str, keyword: str) -> bool:
    return keyword.lower() in text.lower()


def _infer_scope(text: str, table_titles: dict[str, Any]) -> str:
    scope_keywords = table_titles.get("scope_keywords", {})
    parent_keywords = scope_keywords.get("parent", []) or []
    consolidated_keywords = scope_keywords.get("consolidated", []) or []

    if any(_contains_keyword(text, keyword) for keyword in consolidated_keywords):
        return "consolidated"
    if any(_contains_keyword(text, keyword) for keyword in parent_keywords):
        return "parent"
    return "unknown"


def _content_rule_match(text: str, role: str) -> bool:
    content_patterns = {
        "statement.balance_sheet": [
            "资产总计",
            "负债合计",
            "所有者权益合计",
        ],
        "statement.income_statement": [
            "一、营业总收入",
            "二、营业总成本",
            "五、净利润",
            "净利润（净亏损",
            "综合收益总额",
        ],
        "statement.cash_flow": [
            "一、经营活动产生的现金流量",
            "经营活动产生的现金流量：",
            "销售商品、提供劳务收到的现金",
            "筹资活动现金流入小计",
        ],
    }
    patterns = content_patterns.get(role, [])
    return any(_contains_keyword(text, pattern) for pattern in patterns)


def _classify_raw_table(
    raw_table_id: str,
    page_text: str,
    local_text: str,
    table_titles: dict[str, Any],
) -> TableClassification:
    statement_titles = table_titles.get("statement_titles", {})
    best_role = "unknown"
    best_confidence = 0.0
    best_rule_id: str | None = None
    local_content_role: str | None = None
    context_text = "\n".join(part for part in [page_text, local_text] if part)

    for role, rule in statement_titles.items():
        excludes = rule.get("exclude", []) or []
        if any(_contains_keyword(context_text, keyword) for keyword in excludes):
            continue
        prefer = rule.get("prefer", []) or []
        includes = rule.get("include", []) or []
        if any(_contains_keyword(local_text, keyword) for keyword in prefer):
            confidence = 0.95
            rule_id = f"table_titles.{role}.prefer"
        elif any(_contains_keyword(local_text, keyword) for keyword in includes):
            confidence = 0.85
            rule_id = f"table_titles.{role}.include"
        else:
            continue

        if confidence > best_confidence:
            best_role = str(role)
            best_confidence = confidence
            best_rule_id = rule_id

    if best_confidence == 0.0:
        for role, rule in statement_titles.items():
            excludes = rule.get("exclude", []) or []
            if any(_contains_keyword(context_text, keyword) for keyword in excludes):
                continue
            if _content_rule_match(local_text, str(role)) and local_content_role is None:
                local_content_role = str(role)
                best_role = str(role)
                best_confidence = 0.75
                best_rule_id = f"table_titles.{role}.content"

    for role, rule in statement_titles.items():
        if _content_rule_match(local_text, str(role)) and local_content_role is None:
            local_content_role = str(role)
        if local_content_role is not None and local_content_role != str(role):
            continue

        excludes = rule.get("exclude", []) or []
        if any(_contains_keyword(context_text, keyword) for keyword in excludes):
            continue

        prefer = rule.get("prefer", []) or []
        if any(_contains_keyword(page_text, keyword) for keyword in prefer):
            confidence = 0.95
            rule_id = f"table_titles.{role}.prefer"
        else:
            includes = rule.get("include", []) or []
            if any(_contains_keyword(page_text, keyword) for keyword in includes):
                confidence = 0.85
                rule_id = f"table_titles.{role}.include"
            else:
                continue

        if confidence > best_confidence:
            best_role = str(role)
            best_confidence = confidence
            best_rule_id = rule_id

    scope = _infer_scope(context_text, table_titles)
    requires_review = best_confidence < 0.95 or scope != "consolidated"
    return TableClassification(
        raw_table_id=raw_table_id,
        table_role=best_role,
        statement_scope=scope,
        confidence=best_confidence,
        rule_id=best_rule_id,
        requires_review=requires_review,
    )


def classify_tables_for_run(
    conn: Connection,
    extraction_run_id: str,
    *,
    rules_root: Path,
) -> TableClassificationSummary:
    report_id, market = _get_run_context(conn, extraction_run_id)
    rule_pack = load_market_rule_pack(rules_root, market)

    raw_tables = conn.execute(
        """
        select raw_table_id, raw_table_text, page_number
        from raw_tables
        where extraction_run_id = ?
        order by page_number, table_index_on_page
        """,
        (extraction_run_id,),
    ).fetchall()

    classifications = [
        _classify_raw_table(
            str(raw_table_id),
            _page_text_sample(conn, report_id, int(page_number)) or "",
            _local_table_text(conn, str(raw_table_id), raw_table_text),
            rule_pack.table_titles,
        )
        for raw_table_id, raw_table_text, page_number in raw_tables
    ]

    conn.execute(
        "delete from classified_tables where extraction_run_id = ?",
        (extraction_run_id,),
    )
    conn.executemany(
        """
        insert into classified_tables (
          classified_table_id, raw_table_id, extraction_run_id, table_role,
          statement_scope, classification_confidence, classification_rule_id,
          requires_review, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                str(uuid.uuid4()),
                classification.raw_table_id,
                extraction_run_id,
                classification.table_role,
                classification.statement_scope,
                classification.confidence,
                classification.rule_id,
                1 if classification.requires_review else 0,
                _utc_now_iso(),
            )
            for classification in classifications
        ],
    )
    conn.commit()

    review_required = sum(
        1 for classification in classifications if classification.requires_review
    )
    return TableClassificationSummary(
        extraction_run_id=extraction_run_id,
        classified_count=len(classifications),
        review_required_count=review_required,
    )
