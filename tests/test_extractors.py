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
    adapters = [
        (PdfPlumberExtractor(), "pdfplumber"),
        (CamelotExtractor(), "camelot"),
    ]

    for extractor, expected_name in adapters:
        assert extractor.extractor_name == expected_name
        try:
            extractor.extract_tables(Path("sample.pdf"))
        except NotImplementedError as exc:
            message = str(exc)
            assert expected_name in message.lower()
            assert "implemented after" in message
        else:
            raise AssertionError(f"Expected {expected_name} stub to fail clearly.")
