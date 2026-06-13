"""Run full Meituan HK smoke test pipeline."""
from pathlib import Path
from fin_report_extractor.audit_db import connect_audit_db, initialize_audit_db
from fin_report_extractor.import_pdf import register_pdf
from fin_report_extractor.pdf_profiler import profile_pdf_for_report
from fin_report_extractor.extraction_runs import extract_tables_for_report
from fin_report_extractor.extractors import PdfPlumberExtractor, PyMuPDFExtractor
from fin_report_extractor.table_classifier import classify_tables_for_run
from fin_report_extractor.statement_workbook import export_statement_workbook

pdf_path = Path("data/raw_pdfs/2026042400180_c.pdf")
tmp = Path("data/raw_pdfs/meituan_test")
tmp.mkdir(parents=True, exist_ok=True)
audit_db = tmp / "audit.sqlite"

conn = connect_audit_db(audit_db)
initialize_audit_db(conn)

report_id = register_pdf(conn, pdf_path, stored_pdf_path=str(pdf_path.resolve()),
    market="hk", company_id="03690", company_name="美团",
    fiscal_year=2025, report_type="annual")

profile_pdf_for_report(conn, report_id)

# PdfPlumber first (creates extraction run #1)
summary = extract_tables_for_report(conn, report_id, extractor=PdfPlumberExtractor())
print(f"PdfPlumber: {summary.table_count} tables, run={summary.extraction_run_id}")

# Re-extract with PyMuPDF (creates extraction run #2 — use this one for export)
summary = extract_tables_for_report(conn, report_id, extractor=PyMuPDFExtractor())
print(f"PyMuPDF: {summary.table_count} tables, run={summary.extraction_run_id}")

print(f"Extraction run: {summary.extraction_run_id}")

# Classify
classify_tables_for_run(conn, summary.extraction_run_id, rules_root=Path("rules"))

# Check classification
import sqlite3
c = conn.execute("""
    select table_role, count(*) from classified_tables
    where extraction_run_id=? group by table_role
""", (summary.extraction_run_id,))
print("Classification:")
for role, cnt in c:
    print(f"  {role}: {cnt} tables")

# Export
try:
    output = export_statement_workbook(conn, summary.extraction_run_id)
    print(f"SUCCESS: {output}")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()

conn.close()
