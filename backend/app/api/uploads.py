"""File upload and processing API routes."""

import asyncio
import hashlib
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, status
from supabase import Client
from uuid import uuid4
from app.core.database import get_supabase
from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.openrouter_manager import OpenRouterClient
from app.schemas.uploads import UploadResponse, JobStatusOut
from app.agents.orchestrator import FinancialProcessingOrchestrator
from app.agents.base import LLMConfig

router = APIRouter(prefix="/api", tags=["uploads"])


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

    # Fire off ingestion with new agent-based system
    async def run_ingestion_agent():
        try:
            # Create LLM config with Nemotron 3 Ultra
            llm_config = LLMConfig(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_api_url,
                model=settings.primary_llm_model,
                temperature=0.3,
                max_tokens=2000,
            )

            # Create orchestrator
            orchestrator = FinancialProcessingOrchestrator(llm_config)

            # Parse file based on type
            from app.services.parser import parse_pdf, parse_csv, parse_xlsx

            if ext.lower() == "pdf":
                raw_txs = parse_pdf(file_bytes, bank_code)
            elif ext.lower() == "csv":
                raw_txs = parse_csv(file_bytes, bank_code)
            elif ext.lower() in ["xlsx", "xls"]:
                raw_txs = parse_xlsx(file_bytes, bank_code)
            else:
                raise ValueError(f"Unsupported file type: {ext}")

            if not raw_txs:
                raise ValueError("No transactions found in file")

            # Run through orchestrator pipeline
            result = await orchestrator.process_statement(
                raw_transactions=raw_txs,
                bank_code=bank_code,
                file_type=ext,
            )

            if not result.get("success"):
                db.table("processing_jobs").update({
                    "status": "failed",
                    "error": result.get("error", "Processing failed"),
                }).eq("id", job_id).execute()
                return

            # Insert transactions into database
            transactions = result.get("transactions", [])
            inserted_count = 0

            for tx in transactions:
                try:
                    # Create fingerprint
                    fingerprint = hashlib.sha256(
                        f"{tx['date']}|{tx['amount']}|{tx['raw_merchant']}|{account_id}".encode()
                    ).hexdigest()

                    # Get or create category
                    category_response = db.table("categories").select("id").eq(
                        "name", tx.get("category", "Other")
                    ).limit(1).execute()

                    category_id = None
                    if category_response.data:
                        category_id = category_response.data[0]["id"]
                    else:
                        # Create category if doesn't exist
                        cat_insert = db.table("categories").insert({
                            "name": tx.get("category", "Other"),
                            "user_id": None,
                            "icon": "📌",
                        }).execute()
                        if cat_insert.data:
                            category_id = cat_insert.data[0]["id"]

                    # Insert transaction
                    insert_data = {
                        "user_id": user_id,
                        "account_id": account_id,
                        "date": tx["date"],
                        "amount": tx["amount"],
                        "currency": tx.get("currency", "INR"),
                        "raw_merchant": tx["raw_merchant"],
                        "category_id": category_id,
                        "memo": tx.get("memo", ""),
                        "fingerprint": fingerprint,
                        "confidence_score": tx.get("confidence", 0.5),
                        "is_transfer": False,
                    }

                    db.table("transactions").insert(insert_data).execute()
                    inserted_count += 1
                except Exception as e:
                    print(f"Error inserting transaction: {e}")
                    continue

            # Update job status
            db.table("processing_jobs").update({
                "status": "done",
                "error": None,
                "finished_at": asyncio.get_event_loop().time(),
            }).eq("id", job_id).execute()

            print(f"Job {job_id}: Processed {result.get('parsed_count', 0)}, "
                  f"Valid {result.get('valid_count', 0)}, "
                  f"Inserted {inserted_count}")

        except Exception as e:
            print(f"Ingestion error: {e}")
            db.table("processing_jobs").update({
                "status": "failed",
                "error": str(e),
            }).eq("id", job_id).execute()

    asyncio.create_task(run_ingestion_agent())

    return UploadResponse(
        job_id=job_id,
        status="queued",
        message="Processing started",
    )


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
        return JobStatusOut(
            job_id=job["id"],
            status=job["status"],
            error=job.get("error"),
            created_at=job["created_at"],
            finished_at=job.get("finished_at"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
