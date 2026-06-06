from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Connection

import fitz


@dataclass(frozen=True)
class PdfProfile:
    report_id: str
    page_count: int
    is_text_pdf: bool
    unsupported_reason: str | None
    keyword_page_count: int


_STATEMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "a_share": ("资产负债表", "利润表", "现金流量表", "合并"),
    "hk": (
        "consolidated",
        "statement of financial position",
        "statement of profit or loss",
        "statement of cash flows",
        "綜合",
    ),
    "us": (
        "consolidated",
        "balance sheets",
        "statements of operations",
        "statements of cash flows",
    ),
}

_DEFAULT_KEYWORDS = (
    "资产负债表",
    "利润表",
    "现金流量表",
    "consolidated",
    "balance sheet",
    "statement of financial position",
    "statement of cash flows",
)


def _get_report(conn: Connection, report_id: str) -> tuple[Path, str]:
    row = conn.execute(
        "select stored_pdf_path, market from reports where report_id = ?",
        (report_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown report_id: {report_id}")
    return Path(str(row[0])), str(row[1])


def _page_text_sample(text: str, max_length: int = 1000) -> str | None:
    if not text:
        return None
    sample = text.strip()
    return sample[:max_length] if sample else None


def _has_statement_keywords(text: str, market: str) -> bool:
    lowered = text.lower()
    keywords = _STATEMENT_KEYWORDS.get(market, _DEFAULT_KEYWORDS)
    return any(keyword.lower() in lowered for keyword in keywords)


def _text_density(text_char_count: int, width: float | None, height: float | None) -> float | None:
    if width is None or height is None:
        return None
    area = width * height
    if area <= 0:
        return None
    return text_char_count / area


def profile_pdf_for_report(conn: Connection, report_id: str) -> PdfProfile:
    pdf_path, market = _get_report(conn, report_id)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF path does not exist: {pdf_path}")

    page_rows: list[tuple[object, ...]] = []
    keyword_page_count = 0
    text_page_count = 0

    with fitz.open(pdf_path) as document:
        page_count = int(document.page_count)
        for index, page in enumerate(document, start=1):
            text = page.get_text("text")
            stripped_text = text.strip()
            text_char_count = len(stripped_text)
            if text_char_count > 0:
                text_page_count += 1

            rect = page.rect
            width = float(rect.width) if rect is not None else None
            height = float(rect.height) if rect is not None else None
            has_keywords = _has_statement_keywords(text, market)
            if has_keywords:
                keyword_page_count += 1

            page_rows.append(
                (
                    str(uuid.uuid4()),
                    report_id,
                    index,
                    width,
                    height,
                    text_char_count,
                    _text_density(text_char_count, width, height),
                    1 if has_keywords else 0,
                    _page_text_sample(text),
                )
            )

    is_text_pdf = text_page_count > 0
    unsupported_reason = None if is_text_pdf else "no_text_layer"

    conn.execute(
        """
        update reports
        set page_count = ?, is_text_pdf = ?, unsupported_reason = ?
        where report_id = ?
        """,
        (
            page_count,
            1 if is_text_pdf else 0,
            unsupported_reason,
            report_id,
        ),
    )
    conn.execute("delete from pdf_pages where report_id = ?", (report_id,))
    conn.executemany(
        """
        insert into pdf_pages (
          page_id, report_id, page_number, width, height, text_char_count,
          text_density, has_statement_keywords, page_text_sample
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        page_rows,
    )
    conn.commit()

    return PdfProfile(
        report_id=report_id,
        page_count=page_count,
        is_text_pdf=is_text_pdf,
        unsupported_reason=unsupported_reason,
        keyword_page_count=keyword_page_count,
    )
