# Architecture

## System Overview

The AI-Based Resume Screening System is a cloud-native, decision-support application built as a monorepo with a Next.js 14 frontend and a FastAPI backend.

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js 14)                    │
│  ┌──────────────────┐  ┌────────────────┐  ┌─────────────┐ │
│  │  Candidate Portal │  │Recruiter Portal│  │  Auth Pages │ │
│  │      (M.1)       │  │   (M.1/M.10)   │  │    (M.2)    │ │
│  └────────┬─────────┘  └───────┬────────┘  └──────┬──────┘ │
└───────────┼────────────────────┼──────────────────┼─────────┘
            │           REST API (HTTPS + JWT)       │
┌───────────▼────────────────────▼──────────────────▼─────────┐
│                      BACKEND (FastAPI)                        │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ /auth    │  │ /candidates  │  │       /jobs            │ │
│  │  (M.2)   │  │   (M.1/M.3) │  │     (M.3/M.9)          │ │
│  └──────────┘  └──────┬───────┘  └───────────┬────────────┘ │
│                        │                       │              │
│         ┌──────────────▼───────────────────────▼──────────┐  │
│         │           Background Task Pipeline               │  │
│         │  [M.3] Validate → [M.4] Extract                 │  │
│         │       → [M.5] Anonymise → [M.6] Scan            │  │
│         │       → [M.7] Stage 1 Rank                      │  │
│         │       → [M.8] Stage 2 LLM Score                 │  │
│         │       → [M.9] Persist                           │  │
│         └───────────────────────────────────────────────┘  │  │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │ Supabase PostgreSQL │
                    │  batch_jobs table  │
                    │candidate_evaluations│
                    └────────────────────┘
```

---

## Async Safety Rules

- All CPU-bound work (PyMuPDF, spaCy, sentence-transformers) **must** run inside `asyncio.to_thread()` within FastAPI Background Tasks.
- No blocking I/O is permitted in the async event loop.

## Fault Recovery

On startup, the FastAPI lifespan event scans PostgreSQL for records in `queued`, `extracting`, or `scoring` states and re-enqueues them automatically (see `app/persistence/recovery.py`).

## Security Constraints

- JWT tokens issued on login; 2FA code validated before token grant.
- Role enum: `candidate | recruiter | admin` enforced at the route level.
- Adversarial/prompt-injection resumes are dropped before reaching the LLM to prevent jailbreaks and excessive token spend.
- Automated scores are **advisory only** — human recruiters make final decisions.
