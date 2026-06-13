from pathlib import Path

from fin_report_extractor.extractors import (
    CamelotExtractor,
    ExtractedCell,
    ExtractedTable,
    PdfPlumberExtractor,
    PyMuPDFExtractor,
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


def test_camelot_extractor_returns_empty_list_when_not_installed():
    """CamelotExtractor degrades gracefully when camelot-py is not installed."""
    extractor = CamelotExtractor()
    assert extractor.extractor_name == "camelot"
    tables = extractor.extract_tables(Path("nonexistent.pdf"))
    assert tables == []


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


def test_pymupdf_extractor_keeps_healthy_text_layer_when_hk_font_detected(monkeypatch, tmp_path):
    class FakePage:
        def get_text(self, mode):
            if mode == "text":
                return "CONDENSED CONSOLIDATED STATEMENT OF FINANCIAL POSITION"
            if mode == "dict":
                return {
                    "blocks": [
                        {
                            "type": 0,
                            "lines": [
                                {
                                    "spans": [
                                        {
                                            "text": "Total assets",
                                            "bbox": [10, 10, 100, 20],
                                        },
                                        {
                                            "text": "100",
                                            "bbox": [200, 10, 240, 20],
                                        },
                                    ]
                                }
                            ],
                        }
                    ]
                }
            if mode == "rawdict":
                return {"blocks": []}
            raise AssertionError(f"Unexpected mode: {mode}")

    class FakeDocument:
        def __len__(self):
            return 1

        def __getitem__(self, index):
            assert index == 0
            return FakePage()

        def close(self):
            pass

    import fin_report_extractor.extractors.pymupdf_extractor as module

    monkeypatch.setattr(module.fitz, "open", lambda path: FakeDocument())
    monkeypatch.setattr(module, "detect_big5_hk_encoding", lambda doc: True)
    monkeypatch.setattr(
        module,
        "extract_big5_hk_page_text",
        lambda page: "𣏹R��ま�",
    )

    tables = PyMuPDFExtractor().extract_tables(tmp_path / "sample.pdf")

    assert tables[0].quality == {"method": "pymupdf_dict_text_clustering"}
    assert tables[0].cells == [
        ExtractedCell(0, 0, "Total assets", None, 1),
        ExtractedCell(0, 1, "100", None, 1),
    ]


def test_pymupdf_extractor_keeps_hk_balance_sheet_continuation_text(monkeypatch, tmp_path):
    class FakePage:
        def get_text(self, mode):
            if mode == "text":
                return "\u6b0a\u76ca\n\u6b0a\u76ca\u7e3d\u984d\n\u8ca0\u50b5\n\u8ca0\u50b5\u7e3d\u984d"
            if mode == "dict":
                return {
                    "blocks": [
                        {
                            "type": 0,
                            "lines": [
                                {
                                    "spans": [
                                        {
                                            "text": "\u6b0a\u76ca\u7e3d\u984d",
                                            "bbox": [10, 10, 100, 20],
                                        },
                                        {
                                            "text": "1,211,627",
                                            "bbox": [200, 10, 260, 20],
                                        },
                                    ]
                                }
                            ],
                        }
                    ]
                }
            if mode == "rawdict":
                return {"blocks": []}
            raise AssertionError(f"Unexpected mode: {mode}")

    class FakeDocument:
        def __len__(self):
            return 1

        def __getitem__(self, index):
            assert index == 0
            return FakePage()

        def close(self):
            pass

    import fin_report_extractor.extractors.pymupdf_extractor as module

    monkeypatch.setattr(module.fitz, "open", lambda path: FakeDocument())
    monkeypatch.setattr(module, "detect_big5_hk_encoding", lambda doc: True)
    monkeypatch.setattr(
        module,
        "extract_big5_hk_page_text",
        lambda page: "g*}㛓嶭8",
    )

    tables = PyMuPDFExtractor().extract_tables(tmp_path / "sample.pdf")

    assert tables[0].quality == {"method": "pymupdf_dict_text_clustering"}
    assert tables[0].cells == [
        ExtractedCell(0, 0, "\u6b0a\u76ca\u7e3d\u984d", None, 1),
        ExtractedCell(0, 1, "1,211,627", None, 1),
    ]


def test_merge_columns_merges_close_adjacent_columns():
    from fin_report_extractor.extractors.pymupdf_extractor import _merge_columns

    centers = [10.0, 35.0, 200.0, 225.0]
    cells = [
        ExtractedCell(0, 0, "A", None, 1),
        ExtractedCell(0, 1, "B", None, 1),
        ExtractedCell(0, 2, "100", None, 1),
        ExtractedCell(0, 3, "200", None, 1),
    ]

    new_centers, new_cells = _merge_columns(centers, cells, min_gap=30.0)

    # 10+35 (gap=25 < 30) and 200+225 (gap=25 < 30) both merge
    assert len(new_centers) == 2
    assert len(set(c.column_index for c in new_cells)) == 2


def test_merge_columns_does_not_merge_well_separated_columns():
    from fin_report_extractor.extractors.pymupdf_extractor import _merge_columns

    centers = [10.0, 200.0, 400.0]
    cells = [
        ExtractedCell(0, 0, "A", None, 1),
        ExtractedCell(0, 1, "100", None, 1),
        ExtractedCell(0, 2, "200", None, 1),
    ]

    new_centers, new_cells = _merge_columns(centers, cells, min_gap=30.0)
    assert len(new_centers) == 3


def test_merge_columns_absorbs_footnote_columns():
    from fin_report_extractor.extractors.pymupdf_extractor import _merge_columns

    # Column 1 is footnote (short digit); placed close to value column (col 2)
    centers = [10.0, 100.0, 130.0]
    cells = [
        ExtractedCell(0, 0, "Total assets", None, 1),
        ExtractedCell(0, 1, "1", None, 1),
        ExtractedCell(1, 0, "Total liabilities", None, 1),
        ExtractedCell(1, 1, "2", None, 1),
        ExtractedCell(1, 2, "500,000", None, 1),
    ]

    new_centers, new_cells = _merge_columns(centers, cells, min_gap=30.0)

    # Footnote column (col 1 at 100) is closer to value column (col 2 at 130)
    # than label column (col 0 at 10), so it should merge into the value column
    col_indices = set(c.column_index for c in new_cells if c.raw_text == "1")
    value_indices = set(c.column_index for c in new_cells if c.raw_text == "500,000")
    assert col_indices == value_indices, "Footnote column should merge into nearest non-label column"


def test_merge_columns_two_or_fewer_columns_unchanged():
    from fin_report_extractor.extractors.pymupdf_extractor import _merge_columns

    centers = [10.0, 200.0]
    cells = [ExtractedCell(0, 0, "A", None, 1), ExtractedCell(0, 1, "B", None, 1)]
    new_centers, new_cells = _merge_columns(centers, cells)
    assert new_centers == centers
    assert new_cells == cells
