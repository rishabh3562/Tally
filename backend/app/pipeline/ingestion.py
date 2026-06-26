"""Transaction ingestion pipeline."""

import logging
from uuid import uuid4
from supabase import Client
from app.services.parser import parse_pdf, parse_csv, parse_xlsx
from app.services.deduplicator import fingerprint, filter_duplicates
from app.services.merchant import normalize_merchant
from app.services.categorizer import categorize_transaction, get_category_id

logger = logging.getLogger(__name__)


async def run_ingestion(
    job_id: str,
    file_bytes: bytes,
    file_ext: str,
    bank_code: str,
    account_id: str,
    user_id: str,
    db: Client,
) -> dict:
    """
    Run end-to-end ingestion pipeline.

    Args:
        job_id: Processing job ID
        file_bytes: File contents
        file_ext: File extension (pdf, csv, xlsx)
        bank_code: Bank code for parsing
        account_id: Account UUID
        user_id: User UUID
        db: Supabase client

    Returns:
        Results dict with counts
    """
    try:
        # Update job status
        _update_job_status(db, job_id, "processing")

        # Step 1: Parse file
        logger.info(f"Parsing {file_ext} file for {bank_code}")
        if file_ext.lower() == "pdf":
            raw_transactions = parse_pdf(file_bytes, bank_code)
        elif file_ext.lower() == "csv":
            raw_transactions = parse_csv(file_bytes, bank_code)
        elif file_ext.lower() in ["xlsx", "xls"]:
            raw_transactions = parse_xlsx(file_bytes, bank_code)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")

        if not raw_transactions:
            raise ValueError("No transactions found in file")

        logger.info(f"Parsed {len(raw_transactions)} raw transactions")

        # Step 2: Get existing fingerprints for deduplication
        logger.info("Checking for duplicates")
        existing_fps = _get_existing_fingerprints(db, account_id)

        # Step 3: Deduplicate
        new_txs, skipped_txs = filter_duplicates(
            raw_transactions,
            existing_fps,
            account_id,
        )
        logger.info(f"Dedup: {len(new_txs)} new, {len(skipped_txs)} skipped")

        # Step 4: Normalize merchants
        logger.info("Normalizing merchants")
        for tx in new_txs:
            tx["normalized_merchant"] = await normalize_merchant(
                tx["raw_merchant"], db
            )

        # Step 5: Categorize
        logger.info("Categorizing transactions")
        for tx in new_txs:
            category, confidence = await categorize_transaction(
                tx["normalized_merchant"],
                tx["amount"],
                tx.get("memo"),
                db,
            )
            tx["category_name"] = category
            tx["confidence_score"] = confidence

        # Step 6: Insert into database
        logger.info(f"Inserting {len(new_txs)} transactions")
        inserted = 0
        for tx in new_txs:
            try:
                # Get category ID
                category_id = await get_category_id(
                    tx["category_name"],
                    user_id,
                    db,
                )

                # Insert transaction
                insert_data = {
                    "user_id": user_id,
                    "account_id": account_id,
                    "date": tx["date"].isoformat(),
                    "amount": tx["amount"],
                    "currency": tx["currency"],
                    "raw_merchant": tx["raw_merchant"],
                    "category_id": category_id,
                    "memo": tx.get("memo", ""),
                    "fingerprint": tx["fingerprint"],
                    "confidence_score": tx["confidence_score"],
                    "is_transfer": False,
                }

                response = db.table("transactions").insert(insert_data).execute()
                if response.data:
                    inserted += 1
            except Exception as e:
                logger.error(f"Failed to insert transaction: {str(e)}")
                continue

        # Step 7: Mark job as done
        _update_job_status(db, job_id, "done")

        logger.info(f"Ingestion complete: {inserted} transactions inserted")
        return {
            "job_id": job_id,
            "parsed": len(raw_transactions),
            "duplicates": len(skipped_txs),
            "inserted": inserted,
            "status": "done",
        }

    except Exception as e:
        logger.error(f"Ingestion failed: {str(e)}")
        _update_job_status(db, job_id, "failed", str(e))
        return {
            "job_id": job_id,
            "error": str(e),
            "status": "failed",
        }


def _get_existing_fingerprints(db: Client, account_id: str) -> set[str]:
    """Get all existing transaction fingerprints for an account."""
    try:
        response = db.table("transactions").select("fingerprint").eq(
            "account_id", account_id
        ).execute()
        return {row["fingerprint"] for row in response.data}
    except Exception:
        return set()


def _update_job_status(
    db: Client,
    job_id: str,
    status: str,
    error: str = None,
) -> None:
    """Update processing job status."""
    try:
        update_data = {"status": status}
        if error:
            update_data["error"] = error
        if status == "done":
            from datetime import datetime
            update_data["finished_at"] = datetime.utcnow().isoformat()

        db.table("processing_jobs").update(update_data).eq("id", job_id).execute()
    except Exception as e:
        logger.error(f"Failed to update job status: {str(e)}")
