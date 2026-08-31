"""
sanitisation/adversarial.py — Prompt-injection and adversarial content detection.
Owner: Person 2 (M.6)

Detection targets:
  1. Instruction-override phrases (e.g. "ignore previous instructions", "disregard above")
  2. Hidden text patterns (e.g. white-on-white, zero-width characters)
  3. Abnormal keyword density (keyword stuffing)

Resumes that fail any check are dropped BEFORE reaching the LLM stage
to prevent jailbreaks and excessive token spend.
"""
from __future__ import annotations

# ─── Known injection phrases ──────────────────────────────────────────────────
_INJECTION_PHRASES: list[str] = [
    "ignore previous instructions",
    "disregard the above",
    "ignore all prior",
    "forget everything",
    "you are now",
    "act as if",
    "override your instructions",
    "your new instructions",
    # TODO (Person 2 — M.6): Expand this list.
]

# Keyword stuffing threshold: if any single word appears more than this
# fraction of total word count, flag as stuffed.
_STUFFING_RATIO_THRESHOLD = 0.08


class AdversarialContentError(Exception):
    """Raised when a resume contains adversarial or prompt-injection content."""


def scan(text: str) -> None:
    """
    Scan anonymised resume text for adversarial content.

    Args:
        text: Anonymised plain text of a résumé.

    Raises:
        AdversarialContentError: If any adversarial pattern is detected,
            with a message describing the reason.

    TODO (Person 2 — M.6):
      1. Lowercase text and check for each phrase in _INJECTION_PHRASES.
      2. Check for zero-width characters (\\u200b, \\u200c, \\u200d, \\ufeff).
      3. Tokenise text into words; compute per-word frequency / total_words.
         Raise if any word exceeds _STUFFING_RATIO_THRESHOLD.
      4. Log the rejection reason to the error_log field in the DB.
    """
    raise NotImplementedError("[M.6] scan not yet implemented.")
