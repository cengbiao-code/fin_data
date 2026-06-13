from fin_report_extractor.hk_content_decoder import DecodedCandidate
from fin_report_extractor.pdf_font_inspector import (
    FontFinding,
    PageEncodingReport,
    classify_page_report,
    inspect_document,
    summarize_report,
)


def _font(**overrides):
    values = {
        "resource_name": "F1",
        "base_font": "MHeiHK-Bold",
        "encoding": "ETen-B5-H",
        "has_tounicode": False,
        "is_hk_big5": True,
    }
    values.update(overrides)
    return FontFinding(**values)


def test_classify_page_report_marks_healthy_text_layer():
    page = PageEncodingReport(
        page_number=1,
        font_findings=[],
        text_layer_sample="綜合財務狀況表\n資產總額",
        repaired_sample="綜合財務狀況表\n資產總額",
        decoded_candidates=[],
        notes=[],
    )

    assert classify_page_report(page) == "healthy_text_layer"


def test_classify_page_report_marks_mojibake_repairable():
    mojibake = "綜合現金流量表".encode("big5hkscs").decode("latin1")
    page = PageEncodingReport(
        page_number=1,
        font_findings=[],
        text_layer_sample=mojibake,
        repaired_sample="綜合現金流量表",
        decoded_candidates=[],
        notes=[],
    )

    assert classify_page_report(page) == "mojibake_repairable"


def test_classify_page_report_marks_missing_tounicode_decode_candidate():
    page = PageEncodingReport(
        page_number=1,
        font_findings=[_font()],
        text_layer_sample="ºî¦X²{ª÷¬y¶qªí",
        repaired_sample="ºî¦X²{ª÷¬y¶qªí",
        decoded_candidates=[
            DecodedCandidate(
                strategy="big5hkscs",
                score=0.91,
                preview="綜合現金流量表",
                text="綜合現金流量表",
                reason="HK statement keywords improved",
            )
        ],
        notes=[],
    )

    assert classify_page_report(page) == "missing_tounicode_decode_candidate"


def test_summarize_report_counts_hk_fonts_and_candidates():
    page = PageEncodingReport(
        page_number=1,
        font_findings=[_font(), _font(resource_name="F2", has_tounicode=True)],
        text_layer_sample="",
        repaired_sample="",
        decoded_candidates=[
            DecodedCandidate(
                strategy="big5hkscs",
                score=0.91,
                preview="綜合現金流量表",
                text="綜合現金流量表",
                reason="HK statement keywords improved",
            )
        ],
        notes=[],
    )

    summary = summarize_report([page])

    assert summary == {
        "hk_cmap_font_count": 2,
        "fonts_missing_tounicode": 1,
        "candidate_decoder_count": 1,
    }


def test_inspect_document_adds_decode_candidate_from_content_stream():
    class FakePage:
        def get_text(self, mode):
            assert mode == "text"
            return "bad text"

        def get_fonts(self, full=True):
            assert full is True
            return [(7, "cid", "Type0", "MHeiHK-Bold", "F1", "ETen-B5-H")]

        def get_contents(self):
            return [20]

    class FakeDocument:
        metadata = {"producer": "Adobe InDesign"}

        def __len__(self):
            return 1

        def __getitem__(self, index):
            assert index == 0
            return FakePage()

        def xref_get_key(self, xref, key):
            assert xref == 7
            assert key == "ToUnicode"
            return ("null", "null")

        def xref_stream(self, xref):
            assert xref == 20
            return b"BT /F1 12 Tf <BAEEA658> Tj ET"

    report = inspect_document(FakeDocument(), pdf_path="sample.pdf", pages=[1])

    assert report.classification == "missing_tounicode_decode_candidate"
    assert report.summary["candidate_decoder_count"] == 1
    assert report.pages[0].decoded_candidates[0].preview == "綜合"
