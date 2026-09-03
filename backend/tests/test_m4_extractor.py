"""
test_m4_extractor.py — Unit tests for ingestion/extractor.py (M4)

Run:  cd backend && pytest tests/test_m4_extractor.py -v
"""
from __future__ import annotations

import pytest

from app.ingestion.extractor import ExtractionError, extract_text


class TestExtractText:

    @pytest.mark.unit
    def test_single_page_extracts_text(self, valid_pdf_bytes):
        """Should pull text from a valid 1-page PDF."""
        result = extract_text(valid_pdf_bytes)
        assert isinstance(result, str)
        assert "John Doe" in result

    @pytest.mark.unit 
    # this is the fixture name : multi_page_pdf_bytes
    def test_multi_page_extracts_all(self, multi_page_pdf_bytes):
        """Should get text from every page."""
        result = extract_text(multi_page_pdf_bytes)
        assert "page 1" in result
        assert "page 2" in result
        assert "page 3" in result

    @pytest.mark.unit
    def test_corrupt_pdf_raises(self, corrupt_pdf_bytes):
        with pytest.raises(ExtractionError):
            extract_text(corrupt_pdf_bytes)

    @pytest.mark.unit
    def test_empty_bytes_raises(self, empty_bytes):
        with pytest.raises(ExtractionError, match="(?i)empty"):
            extract_text(empty_bytes)

    @pytest.mark.unit
    def test_non_pdf_raises(self, not_pdf_bytes):
        with pytest.raises(ExtractionError):
            extract_text(not_pdf_bytes)

    @pytest.mark.unit
    def test_return_type_is_str(self, valid_pdf_bytes):
        result = extract_text(valid_pdf_bytes)
        assert type(result) is str

    @pytest.mark.unit
    def test_result_is_stripped(self, valid_pdf_bytes):
        """No leading/trailing whitespace in the output."""
        result = extract_text(valid_pdf_bytes)
        assert result == result.strip()

    @pytest.mark.unit
    def test_whitespace_only_pdf_raises(self):
        """A PDF with only spaces/newlines should raise ExtractionError."""
        from tests.conftest import _make_pdf_with_text

        # PDF that renders but has only whitespace content
        pdf = _make_pdf_with_text("   ")
        with pytest.raises(ExtractionError, match="(?i)no extractable text"):
            extract_text(pdf)
