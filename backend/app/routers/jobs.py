"""Recruiter uploads, persistent job tracking, and ranked results."""
from __future__ import annotations
import io
import json
import uuid
import zipfile
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Response, UploadFile, status
from app.ingestion.validator import ValidationError, check_zip
from app.models import BatchResultsResponse, BatchStatus, BatchStatusResponse, UploadResponse, UserRole
from app.persistence import repository
from app.pipeline import run_batch
from app.security import CurrentUser, require_roles

router = APIRouter()

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_batch(background_tasks: BackgroundTasks, file: UploadFile = File(...), rubric: str = Form(...), user: CurrentUser = Depends(require_roles(UserRole.recruiter, UserRole.admin))) -> UploadResponse:
    try:
        parsed_rubric = json.loads(rubric)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Rubric must be valid JSON.") from exc
    data = await file.read()
    try:
        names = check_zip(data)
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc
    batch_id = str(uuid.uuid4())
    await repository.create_batch_job(batch_id, len(names), parsed_rubric, data, file.filename or "resumes.zip")
    background_tasks.add_task(run_batch, batch_id, data, file.filename or "resumes.zip", parsed_rubric)
    return UploadResponse(batch_id=batch_id, status_url=f"/api/jobs/{batch_id}/status")

@router.get("/{batch_id}/status", response_model=BatchStatusResponse)
async def get_batch_status(batch_id: str, user: CurrentUser = Depends(require_roles(UserRole.recruiter, UserRole.admin, UserRole.candidate))) -> BatchStatusResponse:
    row = await repository.get_batch_status(batch_id)
    if not row: raise HTTPException(404, "Batch not found.")
    total = int(row["total_files"])
    processed = int(row["processed_files"] or 0)
    return BatchStatusResponse(batch_id=str(row["batch_id"]), status=BatchStatus(row["status"]), total_files=total, processed_files=processed, failed_files=int(row["failed_files"] or 0), pre_filtered_count=int(row["pre_filtered_count"] or 0), progress_percentage=round(100 * processed / total, 1) if total else 0)

@router.get("/{batch_id}/results", response_model=BatchResultsResponse)
async def get_batch_results(batch_id: str, user: CurrentUser = Depends(require_roles(UserRole.recruiter, UserRole.admin))) -> BatchResultsResponse:
    row = await repository.get_batch_status(batch_id)
    if not row: raise HTTPException(404, "Batch not found.")
    if row["status"] not in {BatchStatus.completed.value, BatchStatus.failed.value}: raise HTTPException(409, "Batch is still processing.")
    return BatchResultsResponse(batch_id=batch_id, results=await repository.get_batch_results(batch_id))

@router.get("/{batch_id}/candidates/{candidate_id}/resume")
async def download_original_resume(batch_id: str, candidate_id: str, user: CurrentUser = Depends(require_roles(UserRole.recruiter, UserRole.admin))) -> Response:
    context = await repository.get_batch_context(batch_id)
    filename = await repository.get_candidate_filename(batch_id, candidate_id)
    if not context or not filename: raise HTTPException(404, "Original resume not found.")
    if (context["upload_filename"] or "").lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(context["upload_bytes"])) as archive:
            content = archive.read(filename)
    else:
        content = context["upload_bytes"]
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})
