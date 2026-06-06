import sqlite3

import pytest

from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db
from fin_report_extractor.import_pdf import register_pdf
from fin_report_extractor.pdf_profiler import profile_pdf_for_report


def _register_report(tmp_path, *, market="a_share", stored_pdf_path=None):
    conn = connect_audit_db(tmp_path / "audit.sqlite")
    initialize_audit_db(conn)
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample\n")
    report_id = register_pdf(
        conn,
        pdf,
        stored_pdf_path=str(stored_pdf_path or pdf),
        market=market,
    )
    return conn, report_id, pdf


class FakePage:
    def __init__(self, text, width=100.0, height=200.0):
        self._text = text
        self.rect = type("Rect", (), {"width": width, "height": height})()

    def get_text(self, mode="text"):
        assert mode == "text"
        return self._text


class FakeDocument:
    def __init__(self, pages):
        self._pages = pages
        self.page_count = len(pages)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def __iter__(self):
        return iter(self._pages)


def test_profile_pdf_for_report_writes_page_metadata(monkeypatch, tmp_path):
    conn, report_id, pdf = _register_report(tmp_path)

    def fake_open(path):
        assert path == pdf
        return FakeDocument(
            [
                FakePage("目录\n公司简介"),
                FakePage("合并资产负债表\n资产总计"),
            ]
        )

    import fin_report_extractor.pdf_profiler as module

    monkeypatch.setattr(module.fitz, "open", fake_open)

    try:
        profile = profile_pdf_for_report(conn, report_id)

        assert profile.report_id == report_id
        assert profile.page_count == 2
        assert profile.is_text_pdf is True
        assert profile.keyword_page_count == 1

        report = conn.execute(
            "select page_count, is_text_pdf, unsupported_reason from reports where report_id = ?",
            (report_id,),
        ).fetchone()
        assert report == (2, 1, None)

        pages = conn.execute(
            """
            select page_number, width, height, text_char_count, text_density,
                   has_statement_keywords, page_text_sample
            from pdf_pages
            where report_id = ?
            order by page_number
            """,
            (report_id,),
        ).fetchall()

        assert pages[0] == (1, 100.0, 200.0, 7, 7 / 20000, 0, "目录\n公司简介")
        assert pages[1][0:6] == (2, 100.0, 200.0, 12, 12 / 20000, 1)
        assert "合并资产负债表" in pages[1][6]
    finally:
        conn.close()


def test_profile_pdf_for_report_replaces_existing_pages(monkeypatch, tmp_path):
    conn, report_id, pdf = _register_report(tmp_path)
    documents = [
        FakeDocument([FakePage("合并利润表")]),
        FakeDocument([FakePage("page one"), FakePage("page two")]),
    ]

    def fake_open(path):
        assert path == pdf
        return documents.pop(0)

    import fin_report_extractor.pdf_profiler as module

    monkeypatch.setattr(module.fitz, "open", fake_open)

    try:
        first = profile_pdf_for_report(conn, report_id)
        second = profile_pdf_for_report(conn, report_id)

        assert first.page_count == 1
        assert second.page_count == 2
        page_rows = conn.execute(
            "select count(*) from pdf_pages where report_id = ?",
            (report_id,),
        ).fetchone()[0]
        assert page_rows == 2
    finally:
        conn.close()


def test_profile_pdf_for_report_marks_no_text_layer(monkeypatch, tmp_path):
    conn, report_id, pdf = _register_report(tmp_path)

    def fake_open(path):
        assert path == pdf
        return FakeDocument([FakePage("  "), FakePage("")])

    import fin_report_extractor.pdf_profiler as module

    monkeypatch.setattr(module.fitz, "open", fake_open)

    try:
        profile = profile_pdf_for_report(conn, report_id)

        assert profile.is_text_pdf is False
        assert profile.unsupported_reason == "no_text_layer"

        report = conn.execute(
            "select page_count, is_text_pdf, unsupported_reason from reports where report_id = ?",
            (report_id,),
        ).fetchone()
        assert report == (2, 0, "no_text_layer")
    finally:
        conn.close()


def test_profile_pdf_for_report_rejects_unknown_report(tmp_path):
    conn = connect_audit_db(tmp_path / "audit.sqlite")
    initialize_audit_db(conn)
    try:
        with pytest.raises(ValueError, match="Unknown report_id"):
            profile_pdf_for_report(conn, "missing")
    finally:
        conn.close()


def test_profile_pdf_for_report_rejects_missing_pdf(tmp_path):
    conn, report_id, _pdf = _register_report(
        tmp_path,
        stored_pdf_path=tmp_path / "missing.pdf",
    )
    try:
        with pytest.raises(FileNotFoundError, match="PDF path does not exist"):
            profile_pdf_for_report(conn, report_id)

        report = conn.execute(
            "select page_count, is_text_pdf, unsupported_reason from reports where report_id = ?",
            (report_id,),
        ).fetchone()
        assert report == (None, 1, None)
    finally:
        conn.close()


def test_profile_pdf_cli_writes_page_metadata(monkeypatch, tmp_path, capsys):
    from fin_report_extractor.cli import main

    audit_db = tmp_path / "audit.sqlite"
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 sample\n")

    main(
        [
            "import-pdf",
            str(pdf),
            "--audit-db",
            str(audit_db),
            "--stored-pdf-path",
            str(pdf),
            "--market",
            "a_share",
        ]
    )
    report_id = capsys.readouterr().out.strip()

    def fake_open(path):
        assert path == pdf
        return FakeDocument([FakePage("合并现金流量表")])

    import fin_report_extractor.pdf_profiler as module

    monkeypatch.setattr(module.fitz, "open", fake_open)

    main(["profile-pdf", report_id, "--audit-db", str(audit_db)])

    output = capsys.readouterr().out
    assert f"report_id={report_id}" in output
    assert "pages=1" in output
    assert "is_text_pdf=1" in output
    assert "keyword_pages=1" in output

    conn = sqlite3.connect(audit_db)
    try:
        page_count = conn.execute("select count(*) from pdf_pages").fetchone()[0]
    finally:
        conn.close()
    assert page_count == 1
