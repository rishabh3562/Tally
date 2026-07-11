"""Upload and job schemas."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any, Dict


class UploadResponse(BaseModel):
    """Schema for upload response."""
    job_id: str
    status: str  # 'queued' | 'processing' | 'done' | 'failed'
    message: str


class JobStatusOut(BaseModel):
    """Schema for job status response."""
    job_id: str
    status: str
    error: Optional[str] = None
    # Human-readable summary of what happened (e.g. "Imported 481 of 513 ...").
    message: Optional[str] = None
    # Per-stage metrics: parsed / duplicates_skipped / inserted / failed /
    # debit & credit splits / category distribution / sample errors / duration.
    stats: Optional[Dict[str, Any]] = None
    created_at: datetime
    finished_at: Optional[datetime] = None
