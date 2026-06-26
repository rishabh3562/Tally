"""Upload and job schemas."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UploadResponse(BaseModel):
    """Schema for upload response."""
    job_id: str
    status: str  # 'queued' | 'processing' | 'done' | 'failed'
    message: str


class JobStatusOut(BaseModel):
    """Schema for job status response."""
    job_id: str
    status: str
    error: Optional[str]
    created_at: datetime
    finished_at: Optional[datetime]
