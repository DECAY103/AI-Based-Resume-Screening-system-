"""Immediate preview API for Person 2's ingestion and sanitisation pipeline.

This endpoint intentionally stops before ranking or persistence.  It is useful
for checking what a submitted resume becomes after validation, extraction, PII
redaction, and the prompt-injection scan.
"""
from __future__ import annotations

import io
import zipfile

from fastapi import APIRouter, File, UploadFile

from app.ingestion.extractor import ExtractionError, extract_text
from app.ingestion.validator import ValidationError, check_pdf, check_zip
from app.models import ProcessingFileResult, ProcessingResponse
from app.sanitisation.adversarial import scan_safe
from app.sanitisation.anonymiser import anonymise

router = APIRouter()


def _process_pdf(filename: str, pdf_bytes: bytes) -> ProcessingFileResult:
    """Run M.3–M.6 for a single PDF and keep failures visible to the UI."""
    try:
        # ``python-magic`` uses native state and is not safe to invoke from
        # FastAPI's worker thread on every platform. Validation is small and
        # bounded by the upload limit, so keep it on the request thread.
        check_pdf(pdf_bytes)
    except ValidationError as exc:
        return ProcessingFileResult(
            filename=filename,
            status="failed",
            validation_passed=False,
            error=str(exc),
        )

    try:
        extracted_text = extract_text(pdf_bytes)
    except ExtractionError as exc:
        return ProcessingFileResult(
            filename=filename,
            status="failed",
            validation_passed=True,
            error=str(exc),
        )

    anonymised_text = anonymise(extracted_text)
    safety_passed, safety_reason = scan_safe(anonymised_text)
    return ProcessingFileResult(
        filename=filename,
        status="accepted" if safety_passed else "rejected",
        validation_passed=True,
        extracted_text=extracted_text,
        anonymised_text=anonymised_text,
        safety_passed=safety_passed,
        safety_reason=safety_reason or None,
    )


@router.post("/preview", response_model=ProcessingResponse)
async def preview_processing(
    file: UploadFile = File(..., description="A PDF resume or ZIP of PDF resumes"),
) -> ProcessingResponse:
    """Return the direct output of validation, extraction, anonymisation and scan."""
    file_bytes = await file.read()
    filename = file.filename or "uploaded-file"

    if filename.lower().endswith(".zip"):
        try:
            pdf_names = check_zip(file_bytes)
        except ValidationError as exc:
            results = [ProcessingFileResult(
                filename=filename,
                status="failed",
                validation_passed=False,
                error=str(exc),
            )]
            return ProcessingResponse(
                input_type="zip", total_files=1, accepted_files=0, rejected_files=1, files=results
            )

        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            pdf_members = [(name, archive.read(name)) for name in pdf_names]
        results = [
            _process_pdf(member_name, member_bytes)
            for member_name, member_bytes in pdf_members
        ]
        input_type = "zip"
    else:
        results = [_process_pdf(filename, file_bytes)]
        input_type = "pdf"

    accepted_files = sum(result.status == "accepted" for result in results)
    return ProcessingResponse(
        input_type=input_type,
        total_files=len(results),
        accepted_files=accepted_files,
        rejected_files=len(results) - accepted_files,
        files=results,
    )
