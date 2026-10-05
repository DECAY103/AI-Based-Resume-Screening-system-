"""
ingestion/extractor.py — Plain-text extraction from PDF files.
Owner: Person 2 (M.4)

Uses PyMuPDF to extract page text.
Call inside asyncio.to_thread() to avoid blocking the event loop.
"""
from __future__ import annotations

import pymupdf


class ExtractionError(Exception):
    """Raised when text cannot be extracted from a PDF."""


def extract_text(pdf_bytes: bytes) -> str:
    """Extract plain text from a PDF provided as raw bytes.

    Returns concatenated text from all pages.
    Raises ExtractionError if the doc is corrupt or has no extractable text.
    """
    if not pdf_bytes:
        raise ExtractionError("Empty file: no data to extract.")

    doc = None
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

        text_parts = []
        for page in doc:
            text_parts.append(page.get_text("text"))

        full_text = "\n".join(text_parts).strip()

        if not full_text:
            raise ExtractionError("PDF has no extractable text.")

        return full_text

    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(f"Failed to extract text: {exc}") from exc
    finally:
        if doc:
            doc.close()
