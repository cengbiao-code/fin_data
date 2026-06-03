from __future__ import annotations

from pathlib import Path

from fin_report_extractor.extractors.base import ExtractedTable, TableExtractor


class CamelotExtractor(TableExtractor):
    extractor_name = "camelot"

    def extract_tables(self, pdf_path: Path) -> list[ExtractedTable]:
        raise NotImplementedError(
            "Camelot table extraction is implemented after the MVP schema foundation."
        )
