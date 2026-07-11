"""File upload and processing API routes."""

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, status
from supabase import Client
from uuid import uuid4
from app.core.database import get_supabase, get_supabase_client
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.schemas.uploads import UploadResponse, JobStatusOut
from app.services.parser import parse_pdf, parse_csv, parse_xlsx
from app.services.categorizer import categorize_transaction
from app.services.deduplicator import fingerprint
from app.services.storage import archive_statement

logger = logging.getLogger("tally.ingestion")

router = APIRouter(prefix="/api", tags=["uploads"])

# Columns added by migration 001. If the DB hasn't been migrated yet, inserts
# with these keys fail; we strip them and retry so ingestion still works.
_EXTENDED_TX_KEYS = (
    "counterparty", "direction", "upi_transaction_id", "txn_time",
    "funding_source", "source_job_id", "source_file_path", "group_id",
)


def _insert_transactions(db: Client, rows: list[dict]) -> None:
    """Bulk-insert a chunk, retrying without migration-001 columns if needed.

    Raises on a genuine failure so the caller can fall back to row-by-row and
    record which rows failed.
    """
    try:
        db.table("transactions").insert(rows).execute()
    except Exception as e:
        msg = str(e).lower()
        # Precise PostgREST "column doesn't exist" signal — NOT a generic error
        # containing the word "column" (which could be a real constraint error
        # we must not mask by silently dropping fields).
        if "schema cache" in msg or "could not find" in msg:
            stripped = [
                {k: v for k, v in row.items() if k not in _EXTENDED_TX_KEYS}
                for row in rows
            ]
            db.table("transactions").insert(stripped).execute()
            logger.warning(
                "transactions extended columns missing — run migration 001 to "
                "capture UPI id / direction / provenance. Inserted base fields only."
            )
            return
        raise


def _update_job(db: Client, job_id: str, **fields) -> None:
    """Update a processing_jobs row, tolerating a missing `stats` column.

    `stats` is added by a migration (see database_schema.sql). If the column
    isn't there yet, retry without it so job tracking still works.
    """
    try:
        db.table("processing_jobs").update(fields).eq("id", job_id).execute()
    except Exception as e:
        if "stats" in fields:
            fields.pop("stats", None)
            try:
                db.table("processing_jobs").update(fields).eq("id", job_id).execute()
                logger.warning(
                    "processing_jobs.stats column missing — run the migration in "
                    "database_schema.sql to capture per-job metrics"
                )
                return
            except Exception as e2:
                e = e2
        logger.error(f"job {job_id}: failed to update status: {e}")


@router.post("/upload-statement", response_model=UploadResponse)
async def upload_statement(
    file: UploadFile,
    account_id: str = Form(...),
    bank_code: str = Form(default="HDFC"),
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
    settings: object = Depends(get_settings),
):
    """
    Upload a bank statement and start processing.

    Args:
        file: Statement file (PDF, CSV, XLSX)
        account_id: Target account UUID
        bank_code: Bank code for parsing (HDFC, ICICI, SBI, etc.)
        user_id: User UUID from token
        db: Supabase client
        settings: App settings

    Returns:
        Job ID and status
    """
    # Validate file extension
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {settings.allowed_file_types}",
        )

    # Read file
    try:
        file_bytes = await file.read()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}",
        )

    # Check if already processed
    try:
        existing = db.table("processing_jobs").select("id").eq(
            "file_hash", file_hash
        ).eq("user_id", user_id).eq("status", "done").limit(1).execute()

        if existing.data:
            return UploadResponse(
                job_id=existing.data[0]["id"],
                status="done",
                message="File already processed",
            )
    except Exception:
        pass

    # Create job record
    job_id = str(uuid4())
    try:
        db.table("processing_jobs").insert({
            "id": job_id,
            "user_id": user_id,
            "file_hash": file_hash,
            "status": "queued",
        }).execute()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}",
        )

    # Fire off deterministic ingestion in the background. We use a fresh Supabase
    # client (not the request-scoped `db`) because the request context is gone by
    # the time this task runs.
    asyncio.create_task(
        _run_ingestion(job_id, user_id, account_id, ext, bank_code, file_bytes)
    )

    return UploadResponse(
        job_id=job_id,
        status="queued",
        message="Processing started",
    )


async def _run_ingestion(
    job_id: str,
    user_id: str,
    account_id: str,
    ext: str,
    bank_code: str,
    file_bytes: bytes,
) -> None:
    """Parse, dedup, categorize and store a statement — with logging + metrics.

    Every stage is logged and counted; the counts are written back to the job's
    `stats` so the UI can show exactly what happened (and why nothing was
    imported, when that's the case).
    """
    started = time.monotonic()
    db = get_supabase_client()
    stats: dict = {
        "parser": None,
        "parsed": 0,
        "duplicates_skipped": 0,
        "inserted": 0,
        "failed": 0,
        "debit_count": 0,
        "debit_total": 0.0,
        "credit_count": 0,
        "credit_total": 0.0,
        "categories": {},
        "errors": [],
    }

    def finish(status_value: str, message: str, error: str | None = None):
        stats["duration_ms"] = int((time.monotonic() - started) * 1000)
        stats["message"] = message
        _update_job(
            db, job_id,
            status=status_value,
            error=error,
            stats=stats,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info(f"job {job_id}: {status_value.upper()} — {message} | {stats}")

    try:
        _update_job(db, job_id, status="processing")

        # Archive the original file first (best-effort provenance / reprocess).
        source_file_path = archive_statement(db, user_id, job_id, ext, file_bytes)
        stats["source_file_path"] = source_file_path

        logger.info(f"job {job_id}: parsing {ext} (bank_code={bank_code})")

        # 1) Parse (deterministic)
        if ext == "pdf":
            raw_txs = parse_pdf(file_bytes, bank_code)
            stats["parser"] = "gpay/pdf"
        elif ext == "csv":
            raw_txs = parse_csv(file_bytes, bank_code)
            stats["parser"] = f"csv:{bank_code}"
        elif ext in ("xlsx", "xls"):
            raw_txs = parse_xlsx(file_bytes, bank_code)
            stats["parser"] = f"xlsx:{bank_code}"
        else:
            finish("failed", f"Unsupported file type: {ext}", error="unsupported_file_type")
            return

        stats["parsed"] = len(raw_txs)
        logger.info(f"job {job_id}: parsed {len(raw_txs)} transactions")

        if not raw_txs:
            finish(
                "failed",
                "No transactions found. The statement format wasn't recognised — "
                "check the file and bank selection.",
                error="no_transactions_parsed",
            )
            return

        # 2) Deduplicate against what's already stored for this account
        existing = db.table("transactions").select("fingerprint").eq(
            "account_id", account_id
        ).execute()
        existing_fps = {r["fingerprint"] for r in (existing.data or []) if r.get("fingerprint")}

        # 3) Categorize + insert
        category_id_cache: dict[str, str | None] = {}

        def resolve_category_id(name: str) -> str | None:
            if name in category_id_cache:
                return category_id_cache[name]
            cid = None
            try:
                res = db.table("categories").select("id").eq("name", name).is_(
                    "user_id", "null"
                ).limit(1).execute()
                if res.data:
                    cid = res.data[0]["id"]
                else:
                    ins = db.table("categories").insert(
                        {"name": name, "user_id": None}
                    ).execute()
                    if ins.data:
                        cid = ins.data[0]["id"]
            except Exception as e:
                logger.warning(f"job {job_id}: category resolve failed for '{name}': {e}")
            category_id_cache[name] = cid
            return cid

        # Categorization is deterministic per merchant string, so memoize it to
        # avoid ~1 DB lookup per transaction (513 -> ~unique-merchant count).
        merchant_category_cache: dict[str, tuple[str, float]] = {}
        rows: list[dict] = []

        for tx in raw_txs:
            # Prefer the first-class UPI transaction id as the distinguishing
            # token so genuine same-day / same-amount payments aren't collapsed;
            # fall back to the memo for non-UPI statements.
            distinguisher = tx.get("upi_transaction_id") or tx.get("memo", "")
            fp = fingerprint(
                tx["date"], tx["amount"], tx["raw_merchant"], account_id,
                distinguisher,
            )
            if fp in existing_fps:
                stats["duplicates_skipped"] += 1
                continue
            existing_fps.add(fp)

            # Track debit/credit split for the summary.
            if tx["amount"] < 0:
                stats["credit_count"] += 1
                stats["credit_total"] += -tx["amount"]
            else:
                stats["debit_count"] += 1
                stats["debit_total"] += tx["amount"]

            merchant = tx["raw_merchant"]
            if merchant in merchant_category_cache:
                category, confidence = merchant_category_cache[merchant]
            else:
                category, confidence = await categorize_transaction(
                    merchant, tx["amount"], tx.get("memo"), db
                )
                merchant_category_cache[merchant] = (category, confidence)
            stats["categories"][category] = stats["categories"].get(category, 0) + 1

            rows.append({
                "user_id": user_id,
                "account_id": account_id,
                "date": tx["date"].isoformat() if hasattr(tx["date"], "isoformat") else tx["date"],
                "amount": tx["amount"],
                "currency": tx.get("currency", "INR"),
                "raw_merchant": merchant,
                "counterparty": tx.get("counterparty") or merchant,
                "category_id": resolve_category_id(category),
                "memo": tx.get("memo", ""),
                "fingerprint": fp,
                "confidence_score": confidence,
                "is_transfer": False,
                "direction": tx.get("direction"),
                "upi_transaction_id": tx.get("upi_transaction_id"),
                "txn_time": tx.get("txn_time"),
                "funding_source": tx.get("funding_source"),
                "source_job_id": job_id,
                "source_file_path": source_file_path,
            })

        # Bulk insert in chunks (previously 1 round-trip per row -> hundreds).
        CHUNK = 100
        for start in range(0, len(rows), CHUNK):
            chunk = rows[start:start + CHUNK]
            try:
                _insert_transactions(db, chunk)
                stats["inserted"] += len(chunk)
                logger.info(f"job {job_id}: inserted {stats['inserted']}/{len(rows)}")
            except Exception:
                # One bad row shouldn't lose the whole chunk — retry row-by-row
                # and record which ones actually failed.
                for row in chunk:
                    try:
                        _insert_transactions(db, [row])
                        stats["inserted"] += 1
                    except Exception as row_err:
                        stats["failed"] += 1
                        if len(stats["errors"]) < 5:
                            stats["errors"].append(
                                f"{row['raw_merchant']} on {row['date']}: {row_err}"
                            )

        finish(
            "done",
            f"Imported {stats['inserted']} of {stats['parsed']} transactions "
            f"({stats['duplicates_skipped']} duplicates skipped, {stats['failed']} failed).",
        )

    except Exception as e:
        logger.exception(f"job {job_id}: ingestion crashed")
        finish("failed", f"Processing error: {e}", error=str(e))


@router.get("/jobs", response_model=list[JobStatusOut])
async def list_jobs(
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """List the current user's processing jobs, newest first."""
    try:
        response = db.table("processing_jobs").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).limit(100).execute()

        out: list[JobStatusOut] = []
        for job in response.data or []:
            job_stats = job.get("stats") or {}
            out.append(JobStatusOut(
                job_id=job["id"],
                status=job["status"],
                error=job.get("error"),
                message=job_stats.get("message"),
                stats=job_stats or None,
                created_at=job["created_at"],
                finished_at=job.get("finished_at"),
            ))
        return out
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/jobs/{job_id}/transactions")
async def get_job_transactions(
    job_id: str,
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Transactions imported by a specific job (correlation via source_job_id)."""
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    try:
        resp = db.table("transactions").select(
            "id,date,amount,currency,raw_merchant,memo,upi_transaction_id,"
            "direction,categories(name)",
            count="exact",
        ).eq("source_job_id", job_id).eq("user_id", user_id).order(
            "date", desc=True
        ).range(offset, offset + limit - 1).execute()

        items = []
        for r in resp.data or []:
            cat = r.get("categories")
            if isinstance(cat, list):  # tolerate list-shaped embed just in case
                cat = cat[0] if cat else None
            items.append({
                "id": r["id"],
                "date": r["date"],
                "amount": r["amount"],
                "currency": r.get("currency", "INR"),
                "raw_merchant": r.get("raw_merchant"),
                "memo": r.get("memo"),
                "category": cat.get("name") if isinstance(cat, dict) else None,
                "upi_transaction_id": r.get("upi_transaction_id"),
                "direction": r.get("direction"),
            })
        return {"total": resp.count or len(items), "items": items}
    except Exception as e:
        # Most likely cause pre-migration: source_job_id column doesn't exist.
        logger.warning(f"job {job_id}: transactions query failed: {e}")
        return {"total": 0, "items": []}


@router.get("/jobs/{job_id}", response_model=JobStatusOut)
async def get_job_status(
    job_id: str,
    user_id: str = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    """Get status of a processing job."""
    try:
        response = db.table("processing_jobs").select("*").eq(
            "id", job_id
        ).eq("user_id", user_id).limit(1).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        job = response.data[0]
        job_stats = job.get("stats") or {}
        return JobStatusOut(
            job_id=job["id"],
            status=job["status"],
            error=job.get("error"),
            message=job_stats.get("message"),
            stats=job_stats or None,
            created_at=job["created_at"],
            finished_at=job.get("finished_at"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
