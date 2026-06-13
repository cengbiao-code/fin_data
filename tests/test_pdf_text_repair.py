from fin_report_extractor.pdf_text_repair import repair_pdf_text


def _latin1_big5_mojibake(text: str) -> str:
    return text.encode("big5hkscs").decode("latin1")


def test_repair_pdf_text_decodes_hk_big5_statement_title():
    mojibake = _latin1_big5_mojibake("綜合現金流量表")

    assert repair_pdf_text(mojibake) == "綜合現金流量表"


def test_repair_pdf_text_keeps_normal_chinese_text():
    assert repair_pdf_text("合并资产负债表") == "合并资产负债表"


def test_repair_pdf_text_keeps_english_text():
    assert (
        repair_pdf_text("Consolidated statement of financial position")
        == "Consolidated statement of financial position"
    )


def test_repair_pdf_text_decodes_pdfplumber_adobe_cns1_cid_tokens():
    assert repair_pdf_text("(cid:4189)(cid:933)(cid:983)(cid:2370)(cid:1676)") == "綜合收益表"


def test_repair_pdf_text_decodes_pymupdf_adobe_cns1_codepoints():
    assert repair_pdf_text("ၝΥϗूڌ") == "綜合收益表"
    assert repair_pdf_text("ߕྠ 2025 ϋܓజѓ") == "美團 2025 年度報告"


def test_repair_pdf_text_fixes_cmap_residue_chars():
    assert repair_pdf_text("蜎") == "及"


def test_repair_pdf_text_fixes_cmap_residue_in_compound_text():
    assert "及" in repair_pdf_text("權益蜎負債總額")
    assert "/" in repair_pdf_text("融資活動╱所得")


def test_repair_pdf_text_cmap_residue_does_not_change_normal_text():
    assert repair_pdf_text("負債總額") == "負債總額"
    assert repair_pdf_text("權益總額") == "權益總額"
    assert repair_pdf_text("Total assets") == "Total assets"


def test_repair_pdf_text_fixes_cmap_residue_apostrophe():
    assert repair_pdf_text("艴") == "'"
    assert "stockholders'" in repair_pdf_text("Total stockholders艴 equity")
