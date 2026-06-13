from fin_report_extractor.hk_content_decoder import (
    decode_big5_candidates,
    extract_text_operands,
)


def test_decode_big5_candidates_prefers_hkscs_statement_text():
    raw = "綜合現金流量表".encode("big5hkscs")

    candidates = decode_big5_candidates(raw, baseline_text="")

    assert candidates[0].strategy == "big5hkscs"
    assert candidates[0].preview == "綜合現金流量表"
    assert candidates[0].score > 0.8


def test_decode_big5_candidates_penalizes_text_that_does_not_improve_baseline():
    raw = "plain ascii".encode("ascii")

    candidates = decode_big5_candidates(raw, baseline_text="plain ascii")

    assert candidates[0].score < 0.5


def test_extract_text_operands_reads_literal_and_hex_text_showing_bytes():
    content = b"BT /F1 12 Tf (ABC) Tj [<BAEEA658> 20 (DEF)] TJ ET"

    operands = extract_text_operands(content)

    assert operands == [b"ABC", bytes.fromhex("BAEEA658"), b"DEF"]
