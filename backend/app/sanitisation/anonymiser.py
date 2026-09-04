"""
sanitisation/anonymiser.py — PII stripping and entity anonymisation.
Owner: Person 2 (M.5)

Two-pass approach:
  Pass 1 — Regex: strip emails, phone numbers, URLs.
  Pass 2 — spaCy NER (en_core_web_sm): replace PERSON entities.

Placeholders:
  [ANON_NAME]   — PERSON entities
  [ANON_EMAIL]  — email addresses
  [ANON_PHONE]  — phone numbers
  [ANON_URL]    — URLs

Load spaCy once at module level; call anonymise() inside asyncio.to_thread().
"""
from __future__ import annotations

import re

import spacy

# load model once — reused across all requests
nlp = spacy.load("en_core_web_sm")

# regex patterns
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")


def anonymise(text: str) -> str:
    """Strip PII from resume text using regex + spaCy NER.

    Returns anonymised text with placeholders.
    Run inside asyncio.to_thread() — spaCy is synchronous.
    """
    if not text or not text.strip():
        return text

    # pass 1 — regex replacements
    result = _EMAIL_RE.sub("[ANON_EMAIL]", text)
    result = _PHONE_RE.sub("[ANON_PHONE]", result)
    result = _URL_RE.sub("[ANON_URL]", result)

    # pass 2 — spaCy NER (replace PERSON spans, longest first to avoid overlap)
    doc = nlp(result)
    person_spans = [ent for ent in doc.ents if ent.label_ == "PERSON"]

    # replace from end to start so indices stay valid
    for span in sorted(person_spans, key=lambda s: s.start_char, reverse=True):
        result = result[:span.start_char] + "[ANON_NAME]" + result[span.end_char:]

    return result
