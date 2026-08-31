"""
ingestion/extractor.py — Plain-text extraction from PDF files.
Owner: Person 2 (M.4)

Uses PyMuPDF (fitz) to extract page text.
Must be called inside asyncio.to_thread() to avoid blocking the event loop.
"""
from __future__ import annotations


class ExtractionError(Exception):
    """Raised when text cannot be extracted from a PDF."""


def extract_text(pdf_bytes: bytes) -> str:
    """
    Extract plain text from a PDF provided as raw bytes.

    Args:
        pdf_bytes: Raw bytes of a validated PDF file.

    Returns:
        Concatenated plain text of all pages.

    Raises:
        ExtractionError: If the document has no extractable text or is corrupt.

    IMPORTANT: Call this inside asyncio.to_thread() — PyMuPDF is synchronous and
               will block the async event loop if called directly.

    TODO (Person 2 — M.4):
      - Open document with fitz.open(stream=pdf_bytes, filetype="pdf").
      - Iterate pages and accumulate page.get_text("text").
      - Raise ExtractionError if the total extracted text is empty/whitespace.
      - Close the document in a finally block.

    Example:
        import asyncio
        text = await asyncio.to_thread(extract_text, raw_bytes)
    """
    raise NotImplementedError("[M.4] extract_text not yet implemented.")
