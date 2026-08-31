"""
routers/candidates.py — Single-resume upload endpoint for candidates.
Owner: Person 1 (M.1) / Person 2 (M.3)

Endpoints:
  POST /api/candidates/upload — accept a single PDF + job_id, kick off pipeline
"""
import uuid
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status

from app.models import UploadResponse

router = APIRouter()


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Candidate PDF résumé (≤ 5 MB)"),
    job_id: str = Form(..., description="UUID of the target job / rubric"),
) -> UploadResponse:
    """
    Accept a single PDF résumé and enqueue it for processing.

    TODO (Person 2 — M.3): Call validator.check_pdf() on the uploaded file bytes.
    TODO (Person 2 — M.4): Schedule extractor.extract_text() as a background task.
    TODO (Person 2 — M.5): Schedule anonymiser.anonymise() in the task chain.
    TODO (Person 2 — M.6): Schedule adversarial.scan() in the task chain.
    TODO (Person 3 — M.7/M.8): Schedule evaluation pipeline after sanitisation.
    TODO (Person 3 — M.9): Persist initial batch_job record with status=queued.
    """
    batch_id = str(uuid.uuid4())

    # Stub: immediately return 202 with a generated batch_id.
    return UploadResponse(
        batch_id=batch_id,
        status_url=f"/api/jobs/{batch_id}/status",
    )
