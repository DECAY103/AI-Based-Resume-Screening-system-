"""Candidate single-PDF submission against an existing recruiter job rubric."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from app.ingestion.validator import ValidationError, check_pdf
from app.models import UploadResponse, UserRole
from app.persistence import repository
from app.pipeline import run_batch
from app.security import CurrentUser, require_roles

router = APIRouter()

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_resume(background_tasks: BackgroundTasks, file: UploadFile = File(...), job_id: str = Form(...), user: CurrentUser = Depends(require_roles(UserRole.candidate, UserRole.admin))) -> UploadResponse:
    data = await file.read()
    try: check_pdf(data)
    except ValidationError as exc: raise HTTPException(400, str(exc)) from exc
    job = await repository.get_batch_context(job_id)
    if not job: raise HTTPException(404, "Job rubric batch not found.")
    batch_id = str(uuid.uuid4())
    name = file.filename or "resume.pdf"
    await repository.create_batch_job(batch_id, 1, job["rubric"], data, name)
    background_tasks.add_task(run_batch, batch_id, data, name, job["rubric"])
    return UploadResponse(batch_id=batch_id, status_url=f"/api/jobs/{batch_id}/status")
