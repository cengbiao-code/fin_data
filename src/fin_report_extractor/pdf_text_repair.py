from __future__ import annotations

import re
from functools import lru_cache

from pdfminer.cmapdb import CMapDB

_HK_STATEMENT_KEYWORDS = (
    "綜合",
    "資產負債表",
    "財務狀況表",
    "損益表",
    "收益表",
    "現金流量表",
)

_BIG5_HK_FONT_PATTERNS = ("eten-b5-h", "b5-h", "hk", "big5", "adobe-cns1", "cns1")
_PDFPLUMBER_CID_RE = re.compile(r"\(cid:(\d+)\)")


def detect_big5_hk_encoding(doc) -> bool:
    """Scan all page fonts for Hong Kong Big5 CMap indicators.

    Checks font names for patterns like *ETen-B5-H*, *HK*, *Big5*,
    *Adobe-CNS1* which indicate a Big5 HK encoded PDF that PyMuPDF /
    pdfplumber may mis-render due to missing or broken ToUnicode maps.
    """
    for page_num in range(len(doc)):
        page = doc[page_num]
        raw = page.get_text("rawdict")
        for block in raw.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    font = (span.get("font") or "").lower()
                    if any(p in font for p in _BIG5_HK_FONT_PATTERNS):
                        return True
    return False


def _decode_big5_bytes(big5_data: list[int]) -> str:
    """Decode a list of raw Big5 byte values as big5hkscs.

    Values 0-255 are single bytes; values >= 0x10000 are split into
    high and low byte halves (the standard Big5 two-byte pattern).
    """
    raw = bytearray()
    for val in big5_data:
        if val < 256:
            raw.append(val)
        elif val < 0x10000:
            raw.append((val >> 8) & 0xFF)
            raw.append(val & 0xFF)
        else:
            raw.append(63)  # '?'
    for encoding in ("big5hkscs", "big5"):
        try:
            return bytes(raw).decode(encoding, errors="replace")
        except LookupError:
            continue
    return "".join(chr(b) for b in raw)


def extract_big5_hk_page_text(page) -> str:
    """Extract text from a PyMuPDF page using raw CIDs decoded as Big5 HK.

    PyMuPDF's 'rawdict' mode exposes raw character IDs (CIDs) from the
    PDF content stream.  For fonts using Adobe-CNS1 / Big5 HK CMaps,
    these CIDs were stored as two-byte Big5 values that PyMuPDF
    mapped to incorrect Unicode codepoints.  This function groups
    Big5-font characters by position and decodes them via big5hkscs.
    """
    raw = page.get_text("rawdict")
    lines_out: list[str] = []

    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            line_chars: list[dict] = []
            for span in line.get("spans", []):
                font_lower = (span.get("font") or "").lower()
                is_big5 = any(p in font_lower for p in _BIG5_HK_FONT_PATTERNS)
                for ch in span.get("chars", []):
                    line_chars.append(
                        {"c": ch.get("c", ""), "big5": is_big5}
                    )
            if not line_chars:
                continue

            big5_buf: list[int] = []
            out_parts: list[str] = []
            for ch in line_chars:
                if ch["big5"]:
                    big5_buf.append(ord(ch["c"]))
                else:
                    if big5_buf:
                        out_parts.append(_decode_big5_bytes(big5_buf))
                        big5_buf = []
                    out_parts.append(ch["c"])
            if big5_buf:
                out_parts.append(_decode_big5_bytes(big5_buf))

            line_text = "".join(out_parts).strip()
            if line_text:
                lines_out.append(line_text)

    return "\n".join(lines_out)


def _cjk_count(text: str) -> int:
    return sum(1 for char in text if "一" <= char <= "鿿")


def _hk_keyword_count(text: str) -> int:
    return sum(1 for keyword in _HK_STATEMENT_KEYWORDS if keyword in text)


def _decode_latin1_bytes_as_big5(text: str) -> str | None:
    try:
        raw_bytes = text.encode("latin1")
    except UnicodeEncodeError:
        return None
    for encoding in ("big5hkscs", "big5"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


@lru_cache(maxsize=1)
def _adobe_cns1_unicode_map():
    return CMapDB.get_unicode_map("Adobe-CNS1", vertical=False)


def _adobe_cns1_unichr(cid: int) -> str | None:
    try:
        return _adobe_cns1_unicode_map().get_unichr(cid)
    except KeyError:
        return None


def _decode_pdfplumber_cid_tokens(text: str) -> str | None:
    if "(cid:" not in text:
        return None

    changed = False

    def _replace(match: re.Match[str]) -> str:
        nonlocal changed
        decoded = _adobe_cns1_unichr(int(match.group(1)))
        if decoded is None:
            return match.group(0)
        changed = True
        return decoded

    candidate = _PDFPLUMBER_CID_RE.sub(_replace, text)
    return candidate if changed else None


def _looks_like_cns1_cid_char(char: str) -> bool:
    codepoint = ord(char)
    if codepoint < 128:
        return False
    if "一" <= char <= "鿿":
        return False
    if char in "\n\r\t ()[]{}.,:;+-/%–—":
        return False
    return True


def _decode_cns1_codepoint_text(text: str) -> str | None:
    out: list[str] = []
    changed = False
    for char in text:
        if _looks_like_cns1_cid_char(char):
            decoded = _adobe_cns1_unichr(ord(char))
            if decoded is not None:
                out.append(decoded)
                changed = True
                continue
        out.append(char)
    return "".join(out) if changed else None


def _better_repair(original: str, candidate: str | None) -> str:
    if candidate is None:
        return original
    original_score = (_hk_keyword_count(original), _cjk_count(original))
    candidate_score = (_hk_keyword_count(candidate), _cjk_count(candidate))
    if candidate_score > original_score:
        return candidate
    return original


def repair_pdf_text(text: str) -> str:
    """Repair common HK PDF text extraction encodings.

    Covers both Big5/HKSCS mojibake and Adobe-CNS1 CID text exposed as
    literal ``(cid:123)`` tokens or as Unicode codepoints equal to CID values.
    """
    repaired = _better_repair(text, _decode_latin1_bytes_as_big5(text))
    repaired = _better_repair(repaired, _decode_pdfplumber_cid_tokens(repaired))
    repaired = _better_repair(repaired, _decode_cns1_codepoint_text(repaired))
    return repaired
