from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import fitz

from fin_report_extractor.hk_content_decoder import (
    DecodedCandidate,
    decode_content_stream_candidates,
)
from fin_report_extractor.pdf_text_repair import repair_pdf_text


_HK_FONT_PATTERNS = ("eten-b5", "b5-h", "hkscs", "hk", "big5", "adobe-cns1", "cns1")
_HK_STATEMENT_KEYWORDS = (
    "綜合",
    "資產負債表",
    "財務狀況表",
    "損益表",
    "收益表",
    "現金流量表",
)


@dataclass(frozen=True)
class FontFinding:
    resource_name: str
    base_font: str
    encoding: str
    has_tounicode: bool
    is_hk_big5: bool


@dataclass(frozen=True)
class PageEncodingReport:
    page_number: int
    font_findings: list[FontFinding]
    text_layer_sample: str
    repaired_sample: str
    decoded_candidates: list[DecodedCandidate]
    notes: list[str]


@dataclass(frozen=True)
class PdfEncodingReport:
    pdf_path: str
    producer: str | None
    pages_inspected: list[int]
    classification: str
    summary: dict[str, int]
    pages: list[PageEncodingReport]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _keyword_count(text: str) -> int:
    lowered = text.lower()
    return sum(1 for keyword in _HK_STATEMENT_KEYWORDS if keyword.lower() in lowered)


def _looks_hk_big5(*parts: str) -> bool:
    joined = " ".join(part.lower() for part in parts if part)
    return any(pattern in joined for pattern in _HK_FONT_PATTERNS)


def classify_page_report(page: PageEncodingReport) -> str:
    if _keyword_count(page.text_layer_sample) > 0:
        return "healthy_text_layer"
    if _keyword_count(page.repaired_sample) > _keyword_count(page.text_layer_sample):
        return "mojibake_repairable"
    has_hk_font_without_tounicode = any(
        finding.is_hk_big5 and not finding.has_tounicode
        for finding in page.font_findings
    )
    best_candidate_score = max(
        (candidate.score for candidate in page.decoded_candidates),
        default=0.0,
    )
    if has_hk_font_without_tounicode and best_candidate_score >= 0.5:
        return "missing_tounicode_decode_candidate"
    return "unrecoverable_or_ocr_required"


def summarize_report(pages: list[PageEncodingReport]) -> dict[str, int]:
    findings = [finding for page in pages for finding in page.font_findings]
    return {
        "hk_cmap_font_count": sum(1 for finding in findings if finding.is_hk_big5),
        "fonts_missing_tounicode": sum(
            1 for finding in findings if finding.is_hk_big5 and not finding.has_tounicode
        ),
        "candidate_decoder_count": sum(
            len(page.decoded_candidates) for page in pages
        ),
    }


def _classify_report(pages: list[PageEncodingReport]) -> str:
    classifications = [classify_page_report(page) for page in pages]
    for classification in (
        "missing_tounicode_decode_candidate",
        "mojibake_repairable",
        "healthy_text_layer",
    ):
        if classification in classifications:
            return classification
    return "unrecoverable_or_ocr_required"


def _page_numbers(page_count: int, pages: list[int] | None) -> list[int]:
    if pages is None:
        return list(range(1, page_count + 1))
    return [page for page in pages if 1 <= page <= page_count]


def _font_findings(doc, page) -> list[FontFinding]:
    findings: list[FontFinding] = []
    for font in page.get_fonts(full=True):
        xref = int(font[0])
        base_font = str(font[3] or "")
        resource_name = str(font[4] or "")
        encoding = str(font[5] or "")
        tounicode_type, _tounicode_value = doc.xref_get_key(xref, "ToUnicode")
        has_tounicode = tounicode_type != "null"
        findings.append(
            FontFinding(
                resource_name=resource_name,
                base_font=base_font,
                encoding=encoding,
                has_tounicode=has_tounicode,
                is_hk_big5=_looks_hk_big5(base_font, encoding, resource_name),
            )
        )
    return findings


def _content_stream_bytes(doc, page) -> bytes:
    content_refs = page.get_contents()
    if content_refs is None:
        return b""
    if isinstance(content_refs, int):
        content_refs = [content_refs]
    chunks: list[bytes] = []
    for xref in content_refs:
        try:
            stream = doc.xref_stream(int(xref))
        except Exception:
            continue
        if stream:
            chunks.append(stream)
    return b"\n".join(chunks)


def _decoded_candidates_for_page(doc, page, text: str, findings: list[FontFinding]) -> list[DecodedCandidate]:
    has_hk_font_without_tounicode = any(
        finding.is_hk_big5 and not finding.has_tounicode
        for finding in findings
    )
    if not has_hk_font_without_tounicode:
        return []
    candidates = decode_content_stream_candidates(
        _content_stream_bytes(doc, page),
        baseline_text=text,
    )
    return [candidate for candidate in candidates if candidate.score >= 0.5][:1]


def inspect_document(doc, *, pdf_path: str, pages: list[int] | None = None) -> PdfEncodingReport:
    inspected_pages = _page_numbers(len(doc), pages)
    page_reports: list[PageEncodingReport] = []
    for page_number in inspected_pages:
        page = doc[page_number - 1]
        text = page.get_text("text")
        repaired = repair_pdf_text(text)
        findings = _font_findings(doc, page)
        page_reports.append(
            PageEncodingReport(
                page_number=page_number,
                font_findings=findings,
                text_layer_sample=text.strip()[:1000],
                repaired_sample=repaired.strip()[:1000],
                decoded_candidates=_decoded_candidates_for_page(doc, page, text, findings),
                notes=[],
            )
        )
    return PdfEncodingReport(
        pdf_path=pdf_path,
        producer=(getattr(doc, "metadata", None) or {}).get("producer"),
        pages_inspected=inspected_pages,
        classification=_classify_report(page_reports),
        summary=summarize_report(page_reports),
        pages=page_reports,
    )


def inspect_pdf_fonts(pdf_path: Path, *, pages: list[int] | None = None) -> PdfEncodingReport:
    doc = fitz.open(pdf_path)
    try:
        return inspect_document(doc, pdf_path=str(pdf_path), pages=pages)
    finally:
        doc.close()
