from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db
from fin_report_extractor.extraction_runs import extract_tables_for_report
from fin_report_extractor.extractors import PdfPlumberExtractor
from fin_report_extractor.fact_extractor import extract_facts_for_run
from fin_report_extractor.import_pdf import register_pdf
from fin_report_extractor.pdf_profiler import profile_pdf_for_report
from fin_report_extractor.table_classifier import classify_tables_for_run


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

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
