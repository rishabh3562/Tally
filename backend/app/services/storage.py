"""Supabase Storage helpers for archiving original statement files.

Files are written with the service-role client, so the bucket can stay PRIVATE
with no RLS policy. Archiving is best-effort: a Storage failure must never fail
an otherwise-successful ingestion, so callers get ``None`` back on error.
"""

import logging
from typing import Optional

from supabase import Client

from app.core.config import get_settings

logger = logging.getLogger("tally.storage")

_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
}


def archive_statement(
    db: Client,
    user_id: str,
    job_id: str,
    ext: str,
    file_bytes: bytes,
) -> Optional[str]:
    """Upload the original statement to the private bucket.

    Returns the object path (``<user_id>/<job_id>.<ext>``) on success, or None if
    the upload failed (e.g. the bucket doesn't exist yet) — ingestion continues
    either way.
    """
    settings = get_settings()
    bucket = settings.supabase_statements_bucket
    path = f"{user_id}/{job_id}.{ext}"
    try:
        db.storage.from_(bucket).upload(
            path,
            file_bytes,
            {
                "content-type": _CONTENT_TYPES.get(ext, "application/octet-stream"),
                "upsert": "true",
            },
        )
        logger.info("[storage] archived statement to %s/%s", bucket, path)
        return path
    except Exception as e:
        logger.warning(
            "[storage] could not archive statement (%s). Is the private '%s' "
            "bucket created? Ingestion continues without provenance.",
            e, bucket,
        )
        return None
