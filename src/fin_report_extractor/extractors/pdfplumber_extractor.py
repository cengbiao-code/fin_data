from __future__ import annotations

import json
from pathlib import Path

import pdfplumber

from fin_report_extractor.extractors.base import (
    ExtractedCell,
    ExtractedTable,
    TableExtractor,
)
from fin_report_extractor.pdf_text_repair import repair_pdf_text


def _bbox_json(bbox: object) -> str | None:
    if bbox is None:
        return None
    return json.dumps(list(bbox), ensure_ascii=False)


def _cell_text(value: object) -> str | None:
    if value is None:
        return None
    text = repair_pdf_text(str(value))
    return text if text != "" else None


class PdfPlumberExtractor(TableExtractor):
    extractor_name = "pdfplumber"

    def extract_tables(self, pdf_path: Path) -> list[ExtractedTable]:
        extracted_tables: list[ExtractedTable] = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_number = int(page.page_number)
                for table_index, table in enumerate(page.find_tables()):
                    grid = table.extract()
                    cell_bboxes = list(getattr(table, "cells", []) or [])
                    cells: list[ExtractedCell] = []

                    for row_index, row in enumerate(grid):
                        for column_index, raw_text in enumerate(row):
                            flat_index = row_index * len(row) + column_index
                            cell_bbox = (
                                cell_bboxes[flat_index]
                                if flat_index < len(cell_bboxes)
                                else None
                            )
                            cells.append(
                                ExtractedCell(
                                    row_index=row_index,
                                    column_index=column_index,
                                    raw_text=_cell_text(raw_text),
                                    bbox_json=_bbox_json(cell_bbox),
                                    page_number=page_number,
                                )
                            )

                    extracted_tables.append(
                        ExtractedTable(
                            extractor_name=self.extractor_name,
                            page_number=page_number,
                            table_index_on_page=table_index,
                            bbox_json=_bbox_json(getattr(table, "bbox", None)),
                            cells=cells,
                            quality={"table_method": "pdfplumber.find_tables"},
                        )
                    )

        return extracted_tables
