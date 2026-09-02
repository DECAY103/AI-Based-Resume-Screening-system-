"""
ingestion/validator.py — Binary validation for uploaded files.
Owner: Person 2 (M.3)

Checks:
  - Single PDF: magic bytes, MIME type, size limit
  - ZIP archive: compressed size, uncompressed size (zip-bomb guard),
    must contain at least one .pdf member
"""
from __future__ import annotations

import io
import zipfile

import magic

from app.config import settings


class ValidationError(Exception):
    """Raised when a file fails binary or size validation."""


def check_pdf(file_bytes: bytes) -> None:
    """Validate that file_bytes is a valid PDF within size limits.

    Raises ValidationError on any failure.
    """
    if not file_bytes:
        raise ValidationError("Empty file: no data received.")

    # size limit
    max_bytes = settings.max_pdf_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ValidationError(
            f"PDF exceeds size limit: {len(file_bytes)} bytes "
            f"(max {settings.max_pdf_size_mb} MB)."
        )

    # MIME check — python-magic needs bytes, not bytearray
    raw = bytes(file_bytes) if isinstance(file_bytes, bytearray) else file_bytes
    mime = magic.from_buffer(raw, mime=True)
    if mime != "application/pdf":
        raise ValidationError(
            f"Invalid MIME type: expected application/pdf, got {mime}."
        )

    # secondary header guard
    if not file_bytes[:5] == b"%PDF-":
        raise ValidationError("File does not start with %PDF- magic bytes.")


def check_zip(file_bytes: bytes) -> list[str]:
    """Validate a ZIP archive and return the list of .pdf filenames inside.

    Raises ValidationError if the archive is invalid, too large, or has no PDFs.
    """
    if not file_bytes:
        raise ValidationError("Empty file: no data received.")

    # compressed size limit
    max_zip_bytes = settings.max_zip_size_mb * 1024 * 1024
    if len(file_bytes) > max_zip_bytes:
        raise ValidationError(
            f"ZIP exceeds compressed size limit: {len(file_bytes)} bytes "
            f"(max {settings.max_zip_size_mb} MB)."
        )

    # try opening the archive
    try:
        buf = io.BytesIO(file_bytes)
        zf = zipfile.ZipFile(buf)
    except (zipfile.BadZipFile, Exception) as exc:
        raise ValidationError(f"Invalid ZIP archive: {exc}") from exc

    with zf:
        # zip-bomb guard — check total uncompressed size from metadata
        max_uncompressed = settings.max_zip_uncompressed_mb * 1024 * 1024
        total_uncompressed = sum(info.file_size for info in zf.infolist())
        if total_uncompressed > max_uncompressed:
            raise ValidationError(
                f"ZIP uncompressed size exceeds limit: {total_uncompressed} bytes "
                f"(max {settings.max_zip_uncompressed_mb} MB)."
            )

        # collect .pdf members (case-insensitive)
        pdf_names = [
            name for name in zf.namelist()
            if name.lower().endswith(".pdf")
        ]

        if not pdf_names:
            raise ValidationError("ZIP archive contains no PDF files.")

    return pdf_names
