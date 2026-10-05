"""
test_m5_anonymiser.py — Unit tests for sanitisation/anonymiser.py (M5)

Run:  cd backend && pytest tests/test_m5_anonymiser.py -v
"""
from __future__ import annotations

import pytest

from app.sanitisation.anonymiser import anonymise


class TestAnonymise:

    @pytest.mark.unit
    def test_email_replaced(self):
        result = anonymise("Contact me at john@example.com for details.")
        assert "john@example.com" not in result
        assert "[ANON_EMAIL]" in result

    @pytest.mark.unit
    def test_phone_replaced(self):
        result = anonymise("Call me at +1-555-123-4567 anytime.")
        assert "+1-555-123-4567" not in result
        assert "[ANON_PHONE]" in result

    @pytest.mark.unit
    def test_url_replaced(self):
        result = anonymise("Portfolio at https://linkedin.com/in/johndoe")
        assert "https://linkedin.com" not in result
        assert "[ANON_URL]" in result

    @pytest.mark.unit
    def test_multiple_pii_all_replaced(self):
        text = (
            "John Doe, john@example.com, +1-555-123-4567, "
            "https://linkedin.com/in/johndoe"
        )
        result = anonymise(text)
        assert "john@example.com" not in result
        assert "+1-555-123-4567" not in result
        assert "https://linkedin.com" not in result
        assert "[ANON_EMAIL]" in result
        assert "[ANON_PHONE]" in result
        assert "[ANON_URL]" in result

    @pytest.mark.unit
    def test_name_replaced_by_spacy(self):
        """spaCy should detect 'John Smith' as a PERSON entity."""
        result = anonymise("My name is John Smith and I have 5 years experience.")
        assert "[ANON_NAME]" in result

    @pytest.mark.unit
    def test_clean_text_unchanged(self):
        """Text with no PII should come back the same."""
        text = "5 years of experience building REST APIs and web applications."
        result = anonymise(text)
        assert result == text

    @pytest.mark.unit
    def test_empty_string(self):
        assert anonymise("") == ""

    @pytest.mark.unit
    def test_whitespace_only(self):
        assert anonymise("   ") == "   "

    @pytest.mark.unit
    def test_return_type_is_str(self):
        result = anonymise("Some resume text with john@test.com")
        assert type(result) is str

    @pytest.mark.unit
    def test_www_url_replaced(self):
        result = anonymise("Visit www.mysite.com for more info.")
        assert "www.mysite.com" not in result
        assert "[ANON_URL]" in result

    @pytest.mark.unit
    def test_multiple_emails(self):
        text = "Email alice@foo.com or bob@bar.org"
        result = anonymise(text)
        assert result.count("[ANON_EMAIL]") == 2
        assert "alice@foo.com" not in result
        assert "bob@bar.org" not in result
