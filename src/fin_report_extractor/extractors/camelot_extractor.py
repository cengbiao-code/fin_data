from __future__ import annotations

from pathlib import Path

from fin_report_extractor.extractors.base import (
    ExtractedCell,
    ExtractedTable,
    TableExtractor,
)
from fin_report_extractor.pdf_text_repair import repair_pdf_text


class CamelotExtractor(TableExtractor):
    """PDF table extractor using Camelot's ``flavor='stream'`` mode.

    The stream flavor detects table columns by whitespace gaps rather than
    border lines, making it suitable for borderless HK financial tables where
    PdfPlumber (border-based) may not find tables.
    """

    extractor_name = "camelot"

    def extract_tables(self, pdf_path: Path) -> list[ExtractedTable]:
        try:
            import camelot
        except ImportError:
            return []

        tables: list[ExtractedTable] = []

        try:
            extracted = camelot.read_pdf(
                str(pdf_path),
                flavor="stream",
                pages="all",
                edge_tol=50,
                row_tol=10,
            )
        except Exception:
            return []

        for table_idx, table in enumerate(extracted):
            page_num = table.parsing_report.get("page", 1)
            cells: list[ExtractedCell] = []

            for row_idx in range(table.shape[0]):
                for col_idx in range(table.shape[1]):
                    raw_text = str(table.data[row_idx][col_idx]).strip()
                    if not raw_text:
                        continue
                    cells.append(
                        ExtractedCell(
                            row_index=row_idx,
                            column_index=col_idx,
                            raw_text=repair_pdf_text(raw_text),
                            bbox_json=None,
                            page_number=page_num,
                        )
                    )

            if cells:
                tables.append(
                    ExtractedTable(
                        extractor_name="camelot",
                        page_number=page_num,
                        table_index_on_page=table_idx,
                        bbox_json=None,
                        cells=cells,
                        quality={
                            "method": "camelot_stream",
                            "accuracy": getattr(table, "accuracy", None),
                        },
                    )
                )

        return tables
