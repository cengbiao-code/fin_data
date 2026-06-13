from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db
from fin_report_extractor.extraction_runs import extract_tables_for_report
from fin_report_extractor.extractors import PdfPlumberExtractor, PyMuPDFExtractor
from fin_report_extractor.fact_extractor import extract_facts_for_run
from fin_report_extractor.import_pdf import register_pdf
from fin_report_extractor.pdf_font_inspector import inspect_pdf_fonts
from fin_report_extractor.pdf_profiler import profile_pdf_for_report
from fin_report_extractor.review_workbook import export_review_workbook
from fin_report_extractor.statement_workbook import export_statement_workbook
from fin_report_extractor.table_classifier import classify_tables_for_run
from fin_report_extractor.validation_runner import validate_extraction_run


def _init_db(args: argparse.Namespace) -> None:
    audit_path = Path(args.audit_db)
    analytics_path = Path(args.analytics_db)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    analytics_path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect_audit_db(audit_path)
    try:
        initialize_audit_db(conn)
    finally:
        conn.close()

    from fin_report_extractor.analytics_db import initialize_analytics_db

    initialize_analytics_db(analytics_path)
    print(f"Initialized audit DB: {audit_path}")
    print(f"Initialized analytics DB: {analytics_path}")


def _import_pdf(args: argparse.Namespace) -> None:
    audit_path = Path(args.audit_db)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect_audit_db(audit_path)
    try:
        initialize_audit_db(conn)
        report_id = register_pdf(
            conn,
            args.pdf_path,
            stored_pdf_path=args.stored_pdf_path,
            market=args.market,
            company_id=args.company_id,
            company_name=args.company_name,
            fiscal_year=args.fiscal_year,
            report_type=args.report_type,
        )
    finally:
        conn.close()

    print(report_id)


def _extract_tables(args: argparse.Namespace) -> None:
    audit_path = Path(args.audit_db)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect_audit_db(audit_path)
    try:
        initialize_audit_db(conn)
        summary = extract_tables_for_report(
            conn,
            args.report_id,
            extractor=PdfPlumberExtractor(),
        )
    finally:
        conn.close()

    print(
        f"extraction_run_id={summary.extraction_run_id} "
        f"tables={summary.table_count} cells={summary.cell_count}"
    )


def _profile_pdf(args: argparse.Namespace) -> None:
    audit_path = Path(args.audit_db)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect_audit_db(audit_path)
    try:
        initialize_audit_db(conn)
        profile = profile_pdf_for_report(conn, args.report_id)
    finally:
        conn.close()

    print(
        f"report_id={profile.report_id} pages={profile.page_count} "
        f"is_text_pdf={1 if profile.is_text_pdf else 0} "
        f"keyword_pages={profile.keyword_page_count}"
    )


def _classify_tables(args: argparse.Namespace) -> None:
    audit_path = Path(args.audit_db)

    conn = connect_audit_db(audit_path)
    try:
        initialize_audit_db(conn)
        summary = classify_tables_for_run(
            conn,
            args.extraction_run_id,
            rules_root=Path(args.rules_root),
        )
    finally:
        conn.close()

    print(
        f"extraction_run_id={summary.extraction_run_id} "
        f"classified={summary.classified_count} "
        f"review_required={summary.review_required_count}"
    )


def _extract_facts(args: argparse.Namespace) -> None:
    audit_path = Path(args.audit_db)

    conn = connect_audit_db(audit_path)
    try:
        initialize_audit_db(conn)
        summary = extract_facts_for_run(
            conn,
            args.extraction_run_id,
            rules_root=Path(args.rules_root),
        )
    finally:
        conn.close()

    print(
        f"extraction_run_id={summary.extraction_run_id} "
        f"facts={summary.fact_count} needs_review={summary.needs_review_count}"
    )


def _validate_run(args: argparse.Namespace) -> None:
    audit_path = Path(args.audit_db)

    conn = connect_audit_db(audit_path)
    try:
        initialize_audit_db(conn)
        summary = validate_extraction_run(
            conn,
            args.extraction_run_id,
            rules_root=Path(args.rules_root),
        )
    finally:
        conn.close()

    print(
        f"validation_run_id={summary.validation_run_id} "
        f"extraction_run_id={summary.extraction_run_id} "
        f"results={summary.result_count} failed={summary.failed_count}"
    )


def _export_statements(args: argparse.Namespace) -> None:
    audit_path = Path(args.audit_db)

    conn = connect_audit_db(audit_path)
    try:
        initialize_audit_db(conn)
        output_path = export_statement_workbook(
            conn,
            args.extraction_run_id,
            output_path=args.output or None,
        )
    finally:
        conn.close()

    print(output_path)


def _export_review(args: argparse.Namespace) -> None:
    audit_path = Path(args.audit_db)

    conn = connect_audit_db(audit_path)
    try:
        initialize_audit_db(conn)
        output_path = export_review_workbook(
            conn,
            args.extraction_run_id,
            output_path=args.output or None,
        )
    finally:
        conn.close()

    print(output_path)


def _parse_pages(value: str | None) -> list[int] | None:
    if value is None:
        return None
    pages: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part))
    return pages or None


def _format_font_inspection_text(report) -> str:
    lines = [
        f"classification: {report.classification}",
        f"producer: {report.producer or 'unknown'}",
        "pages inspected: " + ",".join(str(page) for page in report.pages_inspected),
        f"hk_cmap_fonts: {report.summary['hk_cmap_font_count']}",
        f"fonts_missing_tounicode: {report.summary['fonts_missing_tounicode']}",
        f"candidate_decoders: {report.summary['candidate_decoder_count']}",
    ]
    for page in report.pages:
        if page.decoded_candidates:
            lines.append(f"page {page.page_number} candidate_preview:")
            for candidate in page.decoded_candidates[:3]:
                lines.append(f"  {candidate.strategy}: {candidate.preview}")
    return "\n".join(lines)


def _inspect_pdf_fonts(args: argparse.Namespace) -> None:
    report = inspect_pdf_fonts(
        Path(args.pdf_path),
        pages=_parse_pages(args.pages),
    )
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=True, indent=2))
    else:
        print(_format_font_inspection_text(report))


def _export_pdf_statements(args: argparse.Namespace) -> None:
    audit_path = Path(args.audit_db)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect_audit_db(audit_path)
    try:
        initialize_audit_db(conn)

        report_id = register_pdf(
            conn,
            args.pdf_path,
            stored_pdf_path=str(Path(args.pdf_path).resolve()),
            market=args.market,
            company_id=args.company_id,
            company_name=args.company_name,
            fiscal_year=args.fiscal_year,
            report_type=args.report_type,
        )

        profile_pdf_for_report(conn, report_id)

        summary = extract_tables_for_report(
            conn,
            report_id,
            extractor=PdfPlumberExtractor(),
        )
        extraction_run_id = summary.extraction_run_id
        extractor_name = "pdfplumber"

        def _classify_and_export(run_id: str) -> Path:
            classify_tables_for_run(
                conn,
                run_id,
                rules_root=Path(args.rules_root),
            )
            return export_statement_workbook(
                conn,
                run_id,
                output_path=args.output or None,
            )

        # HK and other borderless-table PDFs can yield 0 tables with
        # pdfplumber. Some HKEX PDFs also yield numeric-only tables
        # whose labels are recoverable from PyMuPDF text blocks.
        if summary.table_count == 0:
            summary = extract_tables_for_report(
                conn,
                report_id,
                extractor=PyMuPDFExtractor(),
            )
            extraction_run_id = summary.extraction_run_id
            extractor_name = "pymupdf"

        try:
            output_path = _classify_and_export(extraction_run_id)
        except ValueError as exc:
            if extractor_name == "pymupdf" or "报表不完整" not in str(exc):
                raise
            summary = extract_tables_for_report(
                conn,
                report_id,
                extractor=PyMuPDFExtractor(),
            )
            output_path = _classify_and_export(summary.extraction_run_id)
    finally:
        conn.close()

    print(output_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fin-report")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db")
    init_db.add_argument("--audit-db", default="data/db/audit.sqlite")
    init_db.add_argument("--analytics-db", default="data/db/analytics.duckdb")
    init_db.set_defaults(func=_init_db)

    import_pdf = subparsers.add_parser("import-pdf")
    import_pdf.add_argument("pdf_path")
    import_pdf.add_argument("--audit-db", default="data/db/audit.sqlite")
    import_pdf.add_argument("--stored-pdf-path", required=True)
    import_pdf.add_argument("--market", required=True)
    import_pdf.add_argument("--company-id")
    import_pdf.add_argument("--company-name")
    import_pdf.add_argument("--fiscal-year", type=int)
    import_pdf.add_argument("--report-type")
    import_pdf.set_defaults(func=_import_pdf)

    extract_tables = subparsers.add_parser("extract-tables")
    extract_tables.add_argument("report_id")
    extract_tables.add_argument("--audit-db", default="data/db/audit.sqlite")
    extract_tables.set_defaults(func=_extract_tables)

    profile_pdf = subparsers.add_parser("profile-pdf")
    profile_pdf.add_argument("report_id")
    profile_pdf.add_argument("--audit-db", default="data/db/audit.sqlite")
    profile_pdf.set_defaults(func=_profile_pdf)

    classify_tables = subparsers.add_parser("classify-tables")
    classify_tables.add_argument("extraction_run_id")
    classify_tables.add_argument("--audit-db", default="data/db/audit.sqlite")
    classify_tables.add_argument("--rules-root", default="rules")
    classify_tables.set_defaults(func=_classify_tables)

    extract_facts = subparsers.add_parser("extract-facts")
    extract_facts.add_argument("extraction_run_id")
    extract_facts.add_argument("--audit-db", default="data/db/audit.sqlite")
    extract_facts.add_argument("--rules-root", default="rules")
    extract_facts.set_defaults(func=_extract_facts)

    validate_run = subparsers.add_parser("validate-run")
    validate_run.add_argument("extraction_run_id")
    validate_run.add_argument("--audit-db", default="data/db/audit.sqlite")
    validate_run.add_argument("--rules-root", default="rules")
    validate_run.set_defaults(func=_validate_run)

    export_statements = subparsers.add_parser("export-statements")
    export_statements.add_argument("extraction_run_id")
    export_statements.add_argument("--audit-db", default="data/db/audit.sqlite")
    export_statements.add_argument("--output")
    export_statements.set_defaults(func=_export_statements)

    export_review = subparsers.add_parser("export-review")
    export_review.add_argument("extraction_run_id")
    export_review.add_argument("--audit-db", default="data/db/audit.sqlite")
    export_review.add_argument("--output")
    export_review.set_defaults(func=_export_review)

    inspect_fonts = subparsers.add_parser("inspect-pdf-fonts")
    inspect_fonts.add_argument("pdf_path")
    inspect_fonts.add_argument("--pages")
    inspect_fonts.add_argument("--json", action="store_true")
    inspect_fonts.set_defaults(func=_inspect_pdf_fonts)

    export_pdf = subparsers.add_parser("export-pdf-statements")
    export_pdf.add_argument("pdf_path")
    export_pdf.add_argument("--market", required=True)
    export_pdf.add_argument("--company-id")
    export_pdf.add_argument("--company-name")
    export_pdf.add_argument("--fiscal-year", type=int)
    export_pdf.add_argument("--report-type")
    export_pdf.add_argument("--audit-db", default="data/db/audit.sqlite")
    export_pdf.add_argument("--rules-root", default="rules")
    export_pdf.add_argument("--output")
    export_pdf.set_defaults(func=_export_pdf_statements)

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
