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
    TODO (Person 3 — M.7): Run Stage 1 semantic ranking across all valid texts.
    TODO (Person 3 — M.8): Run Stage 2 Gemini evaluation on Top-N.
    TODO (Person 3 — M.9): Persist batch_job + candidate_evaluations records.
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

    TODO (Person 3 — M.9):
      - Query batch_jobs table by batch_id.
      - Aggregate counts from candidate_evaluations.
      - Compute progress_percentage.
      - Return 404 if batch_id is not found.
    """
    # Stub response
    return BatchStatusResponse(
        batch_id=batch_id,
        status=BatchStatus.queued,
    )


@router.get("/{batch_id}/results", response_model=BatchResultsResponse)
async def get_batch_results(batch_id: str) -> BatchResultsResponse:
    """
    Return the ranked leaderboard results for a completed batch.

    TODO (Person 3 — M.9):
      - Verify batch status is "completed".
      - Fetch all candidate_evaluations for the batch, ordered by overall_score DESC.
      - Return 404 if batch not found, 409 if not yet completed.
    """
    # Stub response
    return BatchResultsResponse(batch_id=batch_id, results=[])
