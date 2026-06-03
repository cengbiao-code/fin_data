from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExtractedCell:
    row_index: int
    column_index: int
    raw_text: str | None
    bbox_json: str | None
    page_number: int


@dataclass(frozen=True)
class ExtractedTable:
    extractor_name: str
    page_number: int
    table_index_on_page: int
    bbox_json: str | None
    cells: list[ExtractedCell]
    quality: dict[str, object]


class TableExtractor:
    extractor_name: str

    def extract_tables(self, pdf_path: Path) -> list[ExtractedTable]:
        raise NotImplementedError
