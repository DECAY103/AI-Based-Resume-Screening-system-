"""Standalone development server for the Person 2 processing preview.

Run ``uvicorn preview_server:app --reload --port 8000`` from ``backend/``.
It deliberately excludes the main application's database lifecycle because the
preview endpoint only validates, extracts, anonymises, and scans uploaded files.
"""
from __future__ import annotations

import os

# The shared settings object also contains values used by later pipeline stages.
# Those stages are not mounted here, so harmless development defaults let this
# focused preview start without a database or Gemini configuration.
os.environ.setdefault("DATABASE_URL", "postgresql://unused:unused@localhost:5432/unused")
os.environ.setdefault("JWT_SECRET", "processing-preview-only")
os.environ.setdefault("GEMINI_API_KEY", "unused")

from fastapi import FastAPI

from app.routers import processing

app = FastAPI(
    title="Resume Processing Preview API",
    description="Person 2 validation, extraction, anonymisation, and safety scan.",
    version="0.1.0",
)
app.include_router(processing.router, prefix="/api/processing", tags=["processing"])


@app.get("/api/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
