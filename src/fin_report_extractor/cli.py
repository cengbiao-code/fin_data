from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db
from fin_report_extractor.extraction_runs import extract_tables_for_report
from fin_report_extractor.extractors import PdfPlumberExtractor
from fin_report_extractor.import_pdf import register_pdf


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

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
