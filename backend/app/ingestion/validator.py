"""
ingestion/validator.py — Binary validation for uploaded files.
Owner: Person 2 (M.3)

Validates:
  - Single PDF: magic bytes must start with %PDF-
  - ZIP archive: magic bytes (PK\\x03\\x04), compressed size ≤ MAX_ZIP_SIZE_MB,
    uncompressed total size ≤ MAX_ZIP_UNCOMPRESSED_MB
"""
from __future__ import annotations

import io
import zipfile

import magic  # python-magic

from app.config import settings


class ValidationError(Exception):
    """Raised when a file fails binary or size validation."""


def check_pdf(file_bytes: bytes) -> None:
    """
    Validate that file_bytes represents a well-formed PDF.

    Args:
        file_bytes: Raw bytes of the uploaded file.

    Raises:
        ValidationError: If the file is not a valid PDF or exceeds the size limit.

    TODO (Person 2 — M.3):
      - Check len(file_bytes) <= settings.max_pdf_size_mb * 1024 * 1024.
      - Use magic.from_buffer(file_bytes, mime=True) → expect "application/pdf".
      - Check file_bytes[:5] == b"%PDF-" as a secondary guard.
    """
    raise NotImplementedError("[M.3] check_pdf not yet implemented.")


def check_zip(file_bytes: bytes) -> list[str]:
    """
    Validate a ZIP archive and return the list of PDF filenames inside.

    Args:
        file_bytes: Raw bytes of the uploaded ZIP file.

    Returns:
        List of PDF filenames found in the archive.

    Raises:
        ValidationError: If the archive is invalid, too large, or contains no PDFs.

    TODO (Person 2 — M.3):
      - Check compressed size <= settings.max_zip_size_mb * 1024 * 1024.
      - Use zipfile.ZipFile to open and inspect members.
      - Sum uncompressed sizes → reject if > MAX_ZIP_UNCOMPRESSED_MB.
      - Return list of .pdf member names (case-insensitive).
    """
    raise NotImplementedError("[M.3] check_zip not yet implemented.")
