from __future__ import annotations

import json
from pathlib import Path

import fitz

from fin_report_extractor.extractors.base import (
    ExtractedCell,
    ExtractedTable,
    TableExtractor,
)
from fin_report_extractor.pdf_text_repair import (
    detect_big5_hk_encoding,
    extract_big5_hk_page_text,
    repair_pdf_text,
)


_HEALTHY_TEXT_KEYWORDS = (
    "consolidated",
    "statement of financial position",
    "income statement",
    "statement of cash flows",
    "total assets",
    "profit for the",
    "cash and cash equivalents",
    "綜合",
    "資產",
    "負債",
    "權益",
    "現金",
)


def _bbox_json(bbox: tuple[float, float, float, float] | None) -> str | None:
    if bbox is None:
        return None
    return json.dumps(list(bbox), ensure_ascii=False)


def _cell_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = repair_pdf_text(str(value))
    return text if text != "" else None


def _has_healthy_text_layer(text: str) -> bool:
    repaired = repair_pdf_text(text)
    lowered = repaired.lower()
    if any(keyword.lower() in lowered for keyword in _HEALTHY_TEXT_KEYWORDS):
        return True
    if not repaired.strip():
        return False
    replacement_count = repaired.count("\ufffd")
    ascii_letter_count = sum(1 for char in repaired if "a" <= char.lower() <= "z")
    return (
        replacement_count / max(len(repaired), 1) < 0.02
        and ascii_letter_count / max(len(repaired), 1) > 0.4
    )


def _cluster(values: list[float], tolerance: float = 3.0) -> list[list[float]]:
    """Cluster nearby float values within *tolerance* of each other."""
    if not values:
        return []
    sorted_vals = sorted(values)
    clusters: list[list[float]] = [[sorted_vals[0]]]
    for v in sorted_vals[1:]:
        if abs(v - clusters[-1][-1]) <= tolerance:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return clusters


def _build_table_from_blocks(
    blocks: list[dict],
    page_number: int,
    table_index: int,
) -> ExtractedTable | None:
    """Build an ExtractedTable from PyMuPDF text blocks on a single page.

    Groups text by y-position proximity into rows, then clusters x-positions
    into columns, producing a grid of ExtractedCells suitable for borderless
    tables common in HK/Asian financial filings.
    """
    # Collect all text spans with their coordinates.
    spans: list[dict] = []
    for block in blocks:
        if block.get("type") != 0:  # not a text block
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = (span.get("text") or "").strip()
                if not text:
                    continue
                spans.append({
                    "text": text,
                    "x0": span.get("bbox", [0, 0, 0, 0])[0],
                    "y": (span.get("bbox", [0, 0, 0, 0])[1]
                          + span.get("bbox", [0, 0, 0, 0])[3]) / 2,
                })

    if not spans:
        return None

    # Cluster spans into rows by vertical position.
    y_vals = [s["y"] for s in spans]
    y_clusters = _cluster(y_vals, tolerance=5.0)

    # Build rows: for each y-cluster, collect all spans whose y is in that cluster.
    rows_data: list[list[dict]] = []
    for cluster in y_clusters:
        y_min = min(cluster)
        y_max = max(cluster)
        row_spans = [
            s for s in spans
            if y_min - 5 <= s["y"] <= y_max + 5
        ]
        if row_spans:
            rows_data.append(row_spans)
            # Remove used spans so each span belongs to one row.
            used = {id(s) for s in row_spans}
            spans = [s for s in spans if id(s) not in used]

    if not rows_data:
        return None

    # Cluster x-positions across all rows to determine global columns.
    # Use a wider tolerance (15.0) than row clustering (5.0) so that
    # nearby numeric columns in financial tables get merged into the
    # same conceptual column — HK reports often align numbers across
    # adjacent sub-columns (e.g. "96,110" and a footnote "2").
    all_x0 = [s["x0"] for row in rows_data for s in row]
    x_clusters = _cluster(all_x0, tolerance=15.0)
    col_centers = [sum(c) / len(c) for c in x_clusters]

    def _find_col(x0: float) -> int:
        """Find the column index closest to *x0*."""
        distances = [abs(x0 - c) for c in col_centers]
        return distances.index(min(distances))

    # Build the cell grid.
    cells: list[ExtractedCell] = []
    for row_idx, row_spans in enumerate(rows_data):
        # Assign each span to a column.
        col_texts: dict[int, list[str]] = {}
        for span in row_spans:
            col = _find_col(span["x0"])
            col_texts.setdefault(col, []).append(span["text"])
        for col_idx in sorted(col_texts):
            text = "".join(col_texts[col_idx])
            cells.append(
                ExtractedCell(
                    row_index=row_idx,
                    column_index=col_idx,
                    raw_text=_cell_text(text),
                    bbox_json=None,
                    page_number=page_number,
                )
            )

    if not cells:
        return None

    return ExtractedTable(
        extractor_name="pymupdf",
        page_number=page_number,
        table_index_on_page=table_index,
        bbox_json=None,
        cells=cells,
        quality={"method": "pymupdf_dict_text_clustering"},
    )


def _build_table_from_raw_text(
    raw_text: str,
    page_number: int,
    table_index: int,
) -> ExtractedTable | None:
    """Build an ExtractedTable from Big5-decoded multi-line text.

    Splits the raw text into lines, then detects tab/space-aligned
    columns by clustering the starting position of each word-like
    token within each line.
    """
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    if not lines:
        return None

    cells: list[ExtractedCell] = []
    for row_idx, line in enumerate(lines):
        # Split on 2+ spaces or tabs — financial tables in HK
        # filings use consistent spacing to align columns.
        parts = [
            p.strip() for p in line.replace("\t", "  ").split("  ")
            if p.strip()
        ]
        for col_idx, text in enumerate(parts):
            cells.append(
                ExtractedCell(
                    row_index=row_idx,
                    column_index=col_idx,
                    raw_text=_cell_text(text),
                    bbox_json=None,
                    page_number=page_number,
                )
            )

    if not cells:
        return None

    return ExtractedTable(
        extractor_name="pymupdf",
        page_number=page_number,
        table_index_on_page=table_index,
        bbox_json=None,
        cells=cells,
        quality={"method": "pymupdf_big5_hk_text"},
    )


class PyMuPDFExtractor(TableExtractor):
    """Table extractor using PyMuPDF (fitz) text-block layout.

    Handles borderless tables common in HK financial filings where
    pdfplumber's line-based detection finds zero tables.
    """

    extractor_name = "pymupdf"

    def extract_tables(self, pdf_path: Path) -> list[ExtractedTable]:
        extracted: list[ExtractedTable] = []

        doc = fitz.open(pdf_path)
        try:
            is_big5_hk = detect_big5_hk_encoding(doc)

            for page_num in range(len(doc)):
                page = doc[page_num]
                page_number = page_num + 1

                if is_big5_hk and not _has_healthy_text_layer(page.get_text("text")):
                    raw_text = extract_big5_hk_page_text(page)
                    # Build a minimal single-table block from the
                    # Big5-decoded raw text.  The coordinate-based
                    # clustering in _build_table_from_blocks won't
                    # work here because rawdict groups chars
                    # differently (no "text" key on spans).
                    table = _build_table_from_raw_text(
                        raw_text, page_number, 0,
                    )
                else:
                    blocks = page.get_text("dict")["blocks"]
                    table = _build_table_from_blocks(
                        blocks, page_number, 0,
                    )

                if table is not None:
                    extracted.append(table)
        finally:
            doc.close()

        return extracted
