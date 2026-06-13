from __future__ import annotations

import re
from dataclasses import dataclass

from pdfminer.pdfinterp import PDFContentParser


_HK_STATEMENT_KEYWORDS = (
    "綜合",
    "資產負債表",
    "財務狀況表",
    "損益表",
    "收益表",
    "現金流量表",
)

_TEXT_OPERAND_PATTERN = re.compile(
    rb"(\((?:\\.|[^\\)])*\)|<[\da-fA-F\s]+>|\[(?:.|\n)*?\])\s*(?:Tj|TJ)"
)
_ARRAY_TEXT_PATTERN = re.compile(rb"\((?:\\.|[^\\)])*\)|<[\da-fA-F\s]+>")

# Keep pdfminer.six as the explicit content-stream parsing dependency for this
# prototype. The small scanner below handles the limited text-showing operands
# we need today and can be replaced with deeper PDFContentParser integration.
PDFMINER_CONTENT_PARSER = PDFContentParser


@dataclass(frozen=True)
class DecodedCandidate:
    strategy: str
    score: float
    preview: str
    text: str
    reason: str


def _cjk_count(text: str) -> int:
    return sum(1 for char in text if "\u4e00" <= char <= "\u9fff")


def _keyword_count(text: str) -> int:
    return sum(1 for keyword in _HK_STATEMENT_KEYWORDS if keyword in text)


def _text_score(text: str) -> float:
    if not text:
        return 0.0
    keyword_score = min(_keyword_count(text) * 0.35, 0.7)
    cjk_score = min(_cjk_count(text) / max(len(text), 1), 1.0) * 0.3
    replacement_penalty = min(text.count("\ufffd") * 0.1, 0.4)
    return max(0.0, min(1.0, keyword_score + cjk_score - replacement_penalty))


def _preview(text: str, max_length: int = 200) -> str:
    return text.strip()[:max_length]


def decode_big5_candidates(raw: bytes, *, baseline_text: str) -> list[DecodedCandidate]:
    candidates: list[DecodedCandidate] = []
    baseline_score = _text_score(baseline_text)

    for encoding in ("big5hkscs", "big5"):
        text = raw.decode(encoding, errors="replace")
        score = _text_score(text)
        if score > baseline_score:
            reason = "HK statement keywords improved"
        else:
            reason = "No improvement over existing text layer"
        candidates.append(
            DecodedCandidate(
                strategy=encoding,
                score=score,
                preview=_preview(text),
                text=text,
                reason=reason,
            )
        )

    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    return candidates


def _literal_to_bytes(token: bytes) -> bytes:
    body = token[1:-1]
    return (
        body.replace(rb"\(", b"(")
        .replace(rb"\)", b")")
        .replace(rb"\\", b"\\")
    )


def _token_to_bytes(token: bytes) -> bytes:
    token = token.strip()
    if token.startswith(b"(") and token.endswith(b")"):
        return _literal_to_bytes(token)
    if token.startswith(b"<") and token.endswith(b">"):
        return bytes.fromhex(re.sub(rb"\s+", b"", token[1:-1]).decode("ascii"))
    return b""


def extract_text_operands(content: bytes) -> list[bytes]:
    operands: list[bytes] = []
    for match in _TEXT_OPERAND_PATTERN.finditer(content):
        token = match.group(1).strip()
        if token.startswith(b"["):
            operands.extend(
                _token_to_bytes(array_match.group(0))
                for array_match in _ARRAY_TEXT_PATTERN.finditer(token)
            )
        else:
            operands.append(_token_to_bytes(token))
    return [operand for operand in operands if operand]


def decode_content_stream_candidates(
    content: bytes,
    *,
    baseline_text: str,
) -> list[DecodedCandidate]:
    raw_text_bytes = b"".join(extract_text_operands(content))
    if not raw_text_bytes:
        return []
    return decode_big5_candidates(raw_text_bytes, baseline_text=baseline_text)
