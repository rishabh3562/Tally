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
from app.pipeline.ingestion_graph import IngestionAgent, IngestionState

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

    # Fire off ingestion with new LangGraph agent
    async def run_ingestion_agent():
        try:
            agent = IngestionAgent(llm_client=OpenRouterClient())
            state: IngestionState = {
                "job_id": job_id,
                "user_id": user_id,
                "account_id": account_id,
                "file_bytes": file_bytes,
                "file_ext": ext,
                "bank_code": bank_code,
                "db": db,
                "llm_client": OpenRouterClient(),
                "raw_transactions": [],
                "parsed_count": 0,
                "deduped_transactions": [],
                "duplicates_skipped": 0,
                "normalized_transactions": [],
                "categorized_transactions": [],
                "inserted_count": 0,
                "errors": [],
                "status": "processing",
            }

            result = await agent.run(state)

            # Update job with final status
            db.table("processing_jobs").update({
                "status": result["status"],
                "error": str(result["errors"]) if result["errors"] else None,
                "finished_at": asyncio.get_event_loop().time(),
            }).eq("id", job_id).execute()
        except Exception as e:
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
