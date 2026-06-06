from pathlib import Path

from fin_report_extractor.extractors import (
    CamelotExtractor,
    ExtractedCell,
    ExtractedTable,
    PdfPlumberExtractor,
    TableExtractor,
)


def test_extracted_cell_captures_grid_position_and_source_page():
    cell = ExtractedCell(
        row_index=1,
        column_index=2,
        raw_text="资产总计",
        bbox_json="[1,2,3,4]",
        page_number=8,
    )

    assert cell.row_index == 1
    assert cell.column_index == 2
    assert cell.raw_text == "资产总计"
    assert cell.bbox_json == "[1,2,3,4]"
    assert cell.page_number == 8


def test_extracted_table_groups_cells_with_extractor_metadata():
    cell = ExtractedCell(
        row_index=0,
        column_index=0,
        raw_text="项目",
        bbox_json=None,
        page_number=8,
    )

    table = ExtractedTable(
        extractor_name="pdfplumber",
        page_number=8,
        table_index_on_page=0,
        bbox_json="[0,0,100,100]",
        cells=[cell],
        quality={"accuracy": 0.98},
    )

    assert table.extractor_name == "pdfplumber"
    assert table.page_number == 8
    assert table.table_index_on_page == 0
    assert table.bbox_json == "[0,0,100,100]"
    assert table.cells == [cell]
    assert table.quality == {"accuracy": 0.98}


def test_table_extractor_base_method_requires_adapter_implementation(tmp_path):
    extractor = TableExtractor()

    try:
        extractor.extract_tables(tmp_path / "sample.pdf")
    except NotImplementedError:
        pass
    else:
        raise AssertionError("Expected TableExtractor.extract_tables to be abstract.")


def test_stub_extractors_fail_clearly_until_real_extraction_is_implemented():
    extractor = CamelotExtractor()

    assert extractor.extractor_name == "camelot"
    try:
        extractor.extract_tables(Path("sample.pdf"))
    except NotImplementedError as exc:
        message = str(exc)
        assert "camelot" in message.lower()
        assert "implemented after" in message
    else:
        raise AssertionError("Expected camelot stub to fail clearly.")


def test_pdfplumber_extractor_reads_tables_from_pdf(monkeypatch, tmp_path):
    class FakeTable:
        bbox = (1, 2, 30, 40)
        cells = [
            (1, 2, 10, 12),
            (10, 2, 30, 12),
            (1, 12, 10, 20),
            None,
        ]

        def extract(self):
            return [
                ["项目", "金额"],
                ["资产总计", ""],
            ]

    class FakePage:
        page_number = 5

        def find_tables(self):
            return [FakeTable()]

    class FakePdf:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    def fake_open(pdf_path):
        assert pdf_path == tmp_path / "sample.pdf"
        return FakePdf()

    import fin_report_extractor.extractors.pdfplumber_extractor as module

    monkeypatch.setattr(module.pdfplumber, "open", fake_open)

    tables = PdfPlumberExtractor().extract_tables(tmp_path / "sample.pdf")

    assert len(tables) == 1
    table = tables[0]
    assert table.extractor_name == "pdfplumber"
    assert table.page_number == 5
    assert table.table_index_on_page == 0
    assert table.bbox_json == "[1, 2, 30, 40]"
    assert table.quality == {"table_method": "pdfplumber.find_tables"}
    assert table.cells == [
        ExtractedCell(0, 0, "项目", "[1, 2, 10, 12]", 5),
        ExtractedCell(0, 1, "金额", "[10, 2, 30, 12]", 5),
        ExtractedCell(1, 0, "资产总计", "[1, 12, 10, 20]", 5),
        ExtractedCell(1, 1, None, None, 5),
    ]
