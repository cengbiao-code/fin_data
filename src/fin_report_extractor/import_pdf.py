from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection


def compute_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def register_pdf(
    conn: Connection,
    pdf_path: str | Path,
    *,
    stored_pdf_path: str,
    market: str,
    company_id: str | None = None,
    company_name: str | None = None,
    fiscal_year: int | None = None,
    report_type: str | None = None,
    is_text_pdf: bool = True,
    unsupported_reason: str | None = None,
) -> str:
    pdf_path = Path(pdf_path)
    file_sha256 = compute_sha256(pdf_path)

    existing = conn.execute(
        "select report_id from reports where file_sha256 = ?",
        (file_sha256,),
    ).fetchone()
    if existing is not None:
        return str(existing[0])

    report_id = str(uuid.uuid4())
    conn.execute(
        """
        insert into reports (
          report_id, file_sha256, original_filename, stored_pdf_path,
          market, company_id, company_name, fiscal_year, report_type,
          source_type, is_text_pdf, unsupported_reason, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            report_id,
            file_sha256,
            pdf_path.name,
            stored_pdf_path,
            market,
            company_id,
            company_name,
            fiscal_year,
            report_type,
            "pdf",
            1 if is_text_pdf else 0,
            unsupported_reason,
            _utc_now_iso(),
        ),
    )
    conn.commit()
    return report_id
