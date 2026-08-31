"""
models.py — Shared Pydantic request/response schemas used across the API.

These models define the contract between the frontend and backend,
and the internal data shapes passed between pipeline stages.
"""
from __future__ import annotations

import enum
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


# ─── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    candidate = "candidate"
    recruiter = "recruiter"
    admin = "admin"


class BatchStatus(str, enum.Enum):
    queued = "queued"
    extracting = "extracting"
    scoring = "scoring"
    pre_filtered = "pre_filtered"
    completed = "completed"
    failed = "failed"


# ─── Auth (M.2) ───────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    message: str = "2FA code sent"
    temp_token: str


class VerifyRequest(BaseModel):
    temp_token: str
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole


# ─── Upload responses (M.3 / M.9) ────────────────────────────────────────────

class UploadResponse(BaseModel):
    batch_id: str
    status_url: str


# ─── Status polling (M.9) ────────────────────────────────────────────────────

class BatchStatusResponse(BaseModel):
    batch_id: str
    status: BatchStatus
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    pre_filtered_count: int = 0
    progress_percentage: float = 0.0


# ─── Evaluation result (M.7 / M.8) ───────────────────────────────────────────

class UnifiedEvaluationSchema(BaseModel):
    """
    Structured output produced by the Gemini Flash LLM (Stage 2).
    Persisted as JSONB in the candidate_evaluations table.
    """
    overall_score: float = Field(..., ge=0.0, le=100.0)
    skill_match_score: float = Field(..., ge=0.0, le=100.0)
    matching_skills: List[str]
    missing_skills: List[str]
    work_experience_score: float = Field(..., ge=0.0, le=100.0)
    verdict_summary: str


class CandidateResult(BaseModel):
    candidate_id: str
    overall_score: float
    skill_match_score: float
    work_experience_score: float
    matching_skills: List[str]
    missing_skills: List[str]
    verdict_summary: str
    cosine_similarity_score: float
    status: BatchStatus


class BatchResultsResponse(BaseModel):
    batch_id: str
    results: List[CandidateResult]
