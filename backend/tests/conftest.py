"""
conftest.py — Shared fixtures for Person 2 tests.

Generates test PDFs/ZIPs programmatically (no binary blobs in git).
Sets dummy env vars so pydantic-settings doesn't complain during import.
"""
from __future__ import annotations

import io
import os
import zipfile

# dummy env vars — set before any app.* import since Settings validates at load time
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402
from fpdf import FPDF  # noqa: E402


# ---------------------------------------------------------------------------
# Mock settings — controls size limits without needing a real .env
# ---------------------------------------------------------------------------

class _MockSettings:
    max_pdf_size_mb: int = 5
    max_zip_size_mb: int = 50
    max_zip_uncompressed_mb: int = 250


@pytest.fixture(autouse=True)
def mock_settings():
    mock = _MockSettings()
    with patch("app.ingestion.validator.settings", mock):
        yield mock


# ---------------------------------------------------------------------------
# PDF helper
# ---------------------------------------------------------------------------

def _make_pdf(text: str = "Sample resume content.", pages: int = 1) -> bytes:
    """Build a minimal valid PDF. Returns bytes (not bytearray)."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    for i in range(pages):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, text=f"{text} (page {i + 1})")
    return bytes(pdf.output())  # fpdf2 returns bytearray, convert for python-magic


def _make_pdf_with_text(text: str) -> bytes:
    """Build a 1-page PDF with exact text (no page suffix appended)."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    if text.strip():
        pdf.cell(0, 10, text=text)
    # if text is only whitespace, we just get a blank page
    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# PDF fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_pdf_bytes() -> bytes:
    return _make_pdf("John Doe - Software Engineer Resume")


@pytest.fixture
def multi_page_pdf_bytes() -> bytes:
    return _make_pdf("Multi-page resume content", pages=3)


@pytest.fixture
def not_pdf_bytes() -> bytes:
    return b"This is just a plain text file, not a PDF."


@pytest.fixture
def corrupt_pdf_bytes() -> bytes:
    """Has %PDF- header but nothing valid after it."""
    return b"%PDF-1.4 this is corrupt garbage data"


@pytest.fixture
def empty_bytes() -> bytes:
    return b""


@pytest.fixture
def oversized_pdf_bytes(mock_settings) -> bytes:
    base = _make_pdf("Oversized resume")
    target_size = (mock_settings.max_pdf_size_mb * 1024 * 1024) + 1024
    padding = b"\n%" + (b"X" * (target_size - len(base))) + b"\n"
    return base + padding


# ---------------------------------------------------------------------------
# ZIP fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_zip_bytes(valid_pdf_bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("resume_alice.pdf", valid_pdf_bytes)
        zf.writestr("resume_bob.pdf", valid_pdf_bytes)
    return buf.getvalue()


@pytest.fixture
def zip_no_pdfs_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("notes.txt", "This is not a PDF")
        zf.writestr("readme.md", "# README")
    return buf.getvalue()


@pytest.fixture
def oversized_zip_bytes(mock_settings) -> bytes:
    target = (mock_settings.max_zip_size_mb * 1024 * 1024) + 1024
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("big_file.pdf", os.urandom(target))
    return buf.getvalue()


@pytest.fixture
def zip_bomb_bytes(mock_settings) -> bytes:
    """Small compressed size, huge uncompressed — zeros compress very well."""
    max_uncompressed = (mock_settings.max_zip_uncompressed_mb * 1024 * 1024) + 1024
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bomb.pdf", b"\x00" * max_uncompressed)
    return buf.getvalue()
