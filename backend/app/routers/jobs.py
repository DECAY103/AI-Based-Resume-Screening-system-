"""
routers/jobs.py — Batch upload, status polling, and results endpoints.
Owner: Person 1 (M.1) + Person 2 (M.3) + Person 3 (M.9)

Endpoints:
  POST /api/jobs/upload          — recruiter batch ZIP upload
  GET  /api/jobs/{batch_id}/status  — real-time progress polling
  GET  /api/jobs/{batch_id}/results — ranked leaderboard results
"""
import uuid
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status

from app.models import BatchResultsResponse, BatchStatus, BatchStatusResponse, UploadResponse
from app.persistence.repository import get_batch_results as fetch_batch_results
from app.persistence.repository import get_batch_status as fetch_batch_status

router = APIRouter()


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_batch(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="ZIP archive of PDF résumés (≤ 50 MB compressed)"),
    rubric: str = Form(..., description="Job rubric as a JSON string"),
) -> UploadResponse:
    """
    Accept a ZIP batch upload and enqueue the full processing pipeline.

    TODO (Person 2 — M.3): Validate ZIP size and magic bytes; unpack; validate each PDF.
    TODO (Person 2 — M.4): Extract text from each PDF inside the ZIP.
    TODO (Person 2 — M.5): Anonymise PII for each extracted text.
    TODO (Person 2 — M.6): Scan each text for adversarial content.
    Pipeline wiring remains pending until M.3–M.6 provide validated, anonymised
    candidate text and a reliable batch file count. The M.7/M.9 interfaces are
    available to that pipeline without fabricating those upstream values here.
    """
    batch_id = str(uuid.uuid4())

    return UploadResponse(
        batch_id=batch_id,
        status_url=f"/api/jobs/{batch_id}/status",
    )


@router.get("/{batch_id}/status", response_model=BatchStatusResponse)
async def get_batch_status(batch_id: str) -> BatchStatusResponse:
    """
    Return current processing progress for a batch.

    """
    batch = await fetch_batch_status(batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")

    total_files = int(batch["total_files"])
    processed_files = int(batch["processed_files"])
    progress_percentage = (
        min(100.0, (processed_files / total_files) * 100.0)
        if total_files > 0
        else 0.0
    )
    return BatchStatusResponse(
        batch_id=batch_id,
        status=BatchStatus(batch["status"]),
        total_files=total_files,
        processed_files=processed_files,
        failed_files=int(batch["failed_files"]),
        pre_filtered_count=int(batch["pre_filtered_count"]),
        progress_percentage=progress_percentage,
    )


@router.get("/{batch_id}/results", response_model=BatchResultsResponse)
async def get_batch_results(batch_id: str) -> BatchResultsResponse:
    """
    Return the ranked leaderboard results for a completed batch.

    """
    batch = await fetch_batch_status(batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")
    if BatchStatus(batch["status"]) is not BatchStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Batch results are available only after completion.",
        )
    return BatchResultsResponse(batch_id=batch_id, results=await fetch_batch_results(batch_id))
