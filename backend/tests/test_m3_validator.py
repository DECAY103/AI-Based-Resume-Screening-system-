"""
test_m3_validator.py — Unit tests for ingestion/validator.py (M3)

Run:  cd backend && pytest tests/test_m3_validator.py -v
"""
from __future__ import annotations

import io
import zipfile

import pytest

from app.ingestion.validator import ValidationError, check_pdf, check_zip


class TestCheckPdf:

    @pytest.mark.unit
    def test_valid_pdf_passes(self, valid_pdf_bytes):
        assert check_pdf(valid_pdf_bytes) is None

    @pytest.mark.unit
    def test_multi_page_pdf_passes(self, multi_page_pdf_bytes):
        assert check_pdf(multi_page_pdf_bytes) is None

    @pytest.mark.unit
    def test_non_pdf_rejected(self, not_pdf_bytes):
        with pytest.raises(ValidationError, match="(?i)mime|invalid"):
            check_pdf(not_pdf_bytes)

    @pytest.mark.unit
    def test_empty_bytes_rejected(self, empty_bytes):
        with pytest.raises(ValidationError, match="(?i)empty"):
            check_pdf(empty_bytes)

    @pytest.mark.unit
    def test_jpeg_rejected(self):
        """JPEG magic bytes — definitely not a PDF."""
        jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
            b"\x00\x01\x00\x00" + b"\x00" * 100
        )
        with pytest.raises(ValidationError, match="(?i)mime|invalid"):
            check_pdf(jpeg)

    @pytest.mark.unit
    def test_oversized_pdf_rejected(self, oversized_pdf_bytes):
        with pytest.raises(ValidationError, match="(?i)size"):
            check_pdf(oversized_pdf_bytes)

    @pytest.mark.unit
    def test_under_limit_passes(self, valid_pdf_bytes, mock_settings):
        """valid_pdf_bytes is well under 5 MB — should pass fine."""
        assert len(valid_pdf_bytes) < mock_settings.max_pdf_size_mb * 1024 * 1024
        check_pdf(valid_pdf_bytes)

    @pytest.mark.unit
    def test_png_rejected(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        with pytest.raises(ValidationError, match="(?i)mime|invalid"):
            check_pdf(png)

    @pytest.mark.unit
    def test_valid_pdf_starts_with_pdf_header(self):
        """Sanity check — generated PDFs do start with %PDF-."""
        from tests.conftest import _make_pdf
        assert _make_pdf("test")[:5] == b"%PDF-"


class TestCheckZip:

    @pytest.mark.unit
    def test_valid_zip_returns_filenames(self, valid_zip_bytes):
        result = check_zip(valid_zip_bytes)
        assert isinstance(result, list)
        assert len(result) == 2
        assert "resume_alice.pdf" in result
        assert "resume_bob.pdf" in result

    @pytest.mark.unit
    def test_no_pdfs_rejected(self, zip_no_pdfs_bytes):
        with pytest.raises(ValidationError, match="(?i)no pdf"):
            check_zip(zip_no_pdfs_bytes)

    @pytest.mark.unit
    def test_non_zip_rejected(self, not_pdf_bytes):
        with pytest.raises(ValidationError, match="(?i)invalid zip|bad"):
            check_zip(not_pdf_bytes)

    @pytest.mark.unit
    def test_empty_bytes_rejected(self, empty_bytes):
        with pytest.raises(ValidationError, match="(?i)empty"):
            check_zip(empty_bytes)

    @pytest.mark.unit
    def test_oversized_zip_rejected(self, oversized_zip_bytes):
        with pytest.raises(ValidationError, match="(?i)size"):
            check_zip(oversized_zip_bytes)

    @pytest.mark.unit
    def test_zip_bomb_rejected(self, zip_bomb_bytes):
        with pytest.raises(ValidationError, match="(?i)uncompressed|size"):
            check_zip(zip_bomb_bytes)

    @pytest.mark.unit
    def test_case_insensitive_pdf_extensions(self):
        """Should find .PDF, .Pdf, .pdf — all of them."""
        from tests.conftest import _make_pdf
        pdf_data = _make_pdf("Case test")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("UPPER.PDF", pdf_data)
            zf.writestr("Mixed.Pdf", pdf_data)
            zf.writestr("lower.pdf", pdf_data)
        assert len(check_zip(buf.getvalue())) == 3

    @pytest.mark.unit
    def test_returns_only_pdf_names(self):
        """Mixed content ZIP — only .pdf names should be returned."""
        from tests.conftest import _make_pdf
        pdf_data = _make_pdf("Mixed content")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("resume.pdf", pdf_data)
            zf.writestr("notes.txt", b"Some notes")
            zf.writestr("cover_letter.pdf", pdf_data)
            zf.writestr("photo.jpg", b"\xff\xd8\xff")
        assert check_zip(buf.getvalue()) == ["resume.pdf", "cover_letter.pdf"]
