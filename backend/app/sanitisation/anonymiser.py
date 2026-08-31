"""
sanitisation/anonymiser.py — PII stripping and entity anonymisation.
Owner: Person 2 (M.5)

Two-pass approach:
  Pass 1 — Regex: strip emails, phone numbers, URLs.
  Pass 2 — spaCy NER (en_core_web_sm): anonymise PERSON and ORG entities.

Placeholders used:
  [ANON_NAME]   — replaces PERSON entities
  [ANON_EMAIL]  — replaces email addresses
  [ANON_PHONE]  — replaces phone numbers
  [ANON_URL]    — replaces URLs
  [ANON_ORG]    — replaces ORG entities (optional, configurable)

IMPORTANT: spaCy model loading is CPU-bound. Load it once at module level
           (nlp = spacy.load(...)) and reuse across requests.
           Call anonymise() inside asyncio.to_thread().
"""
from __future__ import annotations

import re


# TODO (Person 2 — M.5): Load spaCy model once at module level.
# import spacy
# nlp = spacy.load("en_core_web_sm")

# Regex patterns
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")


def anonymise(text: str) -> str:
    """
    Strip PII from extracted resume text using regex + spaCy NER.

    Args:
        text: Plain text extracted from a PDF résumé.

    Returns:
        Anonymised text with PII replaced by placeholders.

    IMPORTANT: Run inside asyncio.to_thread() — spaCy inference is synchronous.

    TODO (Person 2 — M.5):
      1. Apply _EMAIL_RE → replace with "[ANON_EMAIL]".
      2. Apply _PHONE_RE → replace with "[ANON_PHONE]".
      3. Apply _URL_RE   → replace with "[ANON_URL]".
      4. Run nlp(text) and replace PERSON spans with "[ANON_NAME]".
      5. Optionally replace ORG spans with "[ANON_ORG]".
      6. Return the sanitised string.
    """
    raise NotImplementedError("[M.5] anonymise not yet implemented.")
