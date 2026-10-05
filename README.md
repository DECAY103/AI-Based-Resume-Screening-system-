# AI-Based Resume Screening System

A cloud-native, decision-support web application that automates resume parsing, bias reduction, and candidate ranking against recruiter-defined job rubrics.

## Project Purpose

Minimises recruiter screening time and mitigates demographic bias via automated PII stripping and a cost-effective, two-stage evaluation pipeline.

## Contributors

- Harsha B (241IT031)
- Harshith R (241IT032)
- Marthula Venkata Naga Rohith (241IT044)

Department of Information Technology, NITK Surathkal

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (React, App Router, TypeScript) |
| Backend | Python 3.11 · FastAPI |
| Database | Supabase PostgreSQL (asyncpg, pgcrypto) |
| Auth | JWT + 2FA · RBAC |
| PDF Extraction | PyMuPDF (fitz) |
| PII Anonymisation | spaCy `en_core_web_sm` + regex |
| Stage 1 AI | sentence-transformers `all-MiniLM-L6-v2` |
| Stage 2 AI | Google Gemini API (`gemini-2.5-flash`) |

---

## Repository Structure

```
SE-PROJECT/
├── frontend/          # Next.js 14 candidate & recruiter portals (Person 1)
├── backend/           # FastAPI engine
│   └── app/
│       ├── routers/       # HTTP route handlers
│       ├── ingestion/     # PDF validation & text extraction (Person 2)
│       ├── sanitisation/  # PII anonymisation & adversarial detection (Person 2)
│       ├── evaluation/    # Semantic ranking & LLM scoring (Person 3)
│       └── persistence/   # Database CRUD & job recovery (Person 3)
└── docs/              # Architecture & API reference
```

---

## Module Ownership

| Module | Description | Owner |
|--------|-------------|-------|
| M.1 | Candidate upload portal & recruiter dashboard (Next.js) | Person 1 |
| M.2 | JWT + 2FA authentication, RBAC | Person 1 |
| M.3 | Binary magic-byte validation, ZIP size limits | Person 2 |
| M.4 | PyMuPDF plain-text extraction | Person 2 |
| M.5 | PII anonymisation (regex + spaCy NER) | Person 2 |
| M.6 | Adversarial & prompt-injection scanner | Person 2 |
| M.7 | Semantic ranking — sentence-transformers Stage 1 | Person 3 |
| M.8 | LLM evaluation — Gemini Flash Stage 2 | Person 3 |
| M.9 | PostgreSQL persistence & job recovery | Person 3 |
| M.10 | Leaderboard & score breakdown UI | Person 1 |

---

## Processing Pipeline

```
Candidate Upload (PDF / ZIP)
        │
        ▼
[M.3] Validate (magic bytes, size)
        │
        ▼
[M.4] Extract text (PyMuPDF)
        │
        ▼
[M.5] Anonymise PII   →   [M.6] Scan adversarial inputs
        │
        ▼
[M.7] Stage 1 — Semantic cosine similarity (all-MiniLM-L6-v2)
        │  (Top-N + threshold; persist scores and promoted sanitized text)
        ▼
[M.8] Stage 2 — Gemini Flash structured evaluation (validated JSON; configurable retry/backoff)
        │
        ▼
[M.9] Persist Stage 1 and Stage 2 results, counters, status, and recovery state
        │
        ▼
[M.1/M.10] Recruiter Dashboard & Leaderboard
```

---

## Key Data Model

```json
{
  "overall_score": "Float (0.0 – 100.0)",
  "skill_match_score": "Float (0.0 – 100.0)",
  "matching_skills": ["..."],
  "missing_skills": ["..."],
  "work_experience_score": "Float (0.0 – 100.0)",
  "verdict_summary": "Human-readable explanation"
}
```

Stage 1 status: promoted candidates remain `scoring` for the M.8 handoff; all other ranked candidates become `pre_filtered`. Only candidates with a validated M.8 object become `completed`; per-candidate M.8 failures become `failed`. The batch becomes `completed` after all candidate rows reach a terminal state.

## Person 3 pipeline (M.7–M.9)

The integration boundary is `app.evaluation.stage1_pipeline.process_batch(batch_id, sanitized_candidate_texts)`. Call it after M.3–M.6 have validated and anonymized every resume. It reads the batch's stored `rubric`, runs the cached `all-MiniLM-L6-v2` ranker off the event loop, persists Stage 1 scores, and submits only promoted sanitized resume text to M.8. Gemini JSON is validated with `UnifiedEvaluationSchema`; transient provider, malformed JSON, and invalid schema responses use configurable retries. M.9 stores valid results in PostgreSQL and stores per-candidate failures without logging provider exception text.

The canonical names in the checked-in application and migrations are `batch_jobs.rubric`, `candidate_evaluations.sanitized_resume_text`, and `candidate_evaluations.evaluation`. No `PROJECT_RULES.md`, `DECISIONS.md`, SRS, or data dictionary is present in this repository checkout, so those higher-priority contract sources could not be compared. Existing application models and migration names were kept consistent.

### Configuration and setup

Person 3 was developed with **Python 3.11** and PostgreSQL. From a clean checkout, create and activate a virtual environment, then install the declared backend dependencies:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` with real values; the checked-in `.env.example` contains placeholders only. Required application variables are `DATABASE_URL`, `JWT_SECRET`, and `GEMINI_API_KEY`. `GEMINI_MODEL` defaults to `gemini-2.5-flash`; `STAGE2_TIMEOUT_SECONDS` defaults to 60; `STAGE2_MAX_RETRIES` defaults to 2 retries; and `STAGE2_BACKOFF_BASE_SECONDS` defaults to 1 second. M.7 uses `STAGE1_TOP_N` (default 10) and `STAGE1_SIMILARITY_THRESHOLD` (default 0.0, valid range −1 to 1). Keep secrets in environment configuration and out of source control.

Create a PostgreSQL database for development and a separate disposable database for tests. For example, when connected as a PostgreSQL administrator, create `ai_resume_screening` and `ai_resume_screening_test`. Never point `TEST_DATABASE_URL` at production or a database containing valuable data. Apply migrations in numeric filename order from the repository root (the third migration adds a database-level evaluation validity guard):

```powershell
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/app/persistence/migrations/001_initial.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/app/persistence/migrations/002_stage1_handoff.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/app/persistence/migrations/003_validated_evaluation_guard.sql
```

Migration `002_stage1_handoff.sql` is retained as an idempotent upgrade step for databases created before the sanitized handoff column was included in migration 001. On a fresh database, migration 002 is a no-op; keep the numbered migration order for both fresh installs and upgrades.

Set `TEST_DATABASE_URL` in the shell to the disposable test database URL before running PostgreSQL integration tests or database demos, for example `$env:TEST_DATABASE_URL = "postgresql://postgres:<password>@localhost:5432/ai_resume_screening_test"` in PowerShell. The tests verify that the database name contains `test`, apply the idempotent migrations in order, use UUID-scoped rows, and delete their rows afterward. The app itself uses only `DATABASE_URL`; the integration tests and demos use only `TEST_DATABASE_URL`.

From `backend/`, run the suite and demos:

```powershell
python -m pytest -q
python -m pytest -q tests/test_repository_integration.py
python -m tests._demo_stage1_real_model
python -m tests._demo_llm_mock
python -m tests._demo_stage1_database
python -m tests._demo_person3_postgres
```

The real-model demo downloads/loads `all-MiniLM-L6-v2` through sentence-transformers and demonstrates ranking, Top-N, and threshold decisions. The mock Gemini demo requires no key or network. The Stage 1 database demo verifies score persistence and the Stage 2 handoff. The complete Person 3 demo uses the real M.7 model and disposable PostgreSQL, but deliberately mocks only the Gemini provider; it shows ranking, handoff, schema-validated result, persisted rows, and final states, then cleans up its batch. There is no separate real-Gemini demo, so a live Gemini request is not run by these commands.

### Integration boundary and operational notes

The Person 2 handoff is `process_batch(batch_id, sanitized_candidate_texts)`, where `sanitized_candidate_texts` is a mapping from each upstream `candidate_id` (UUID string) to its already anonymized and adversarially scanned `sanitized_text`. Before calling it, upstream code must call `repository.create_batch_job(batch_id, total_files, rubric)` so the batch and rubric are persisted; `total_files` must equal the number of entries in the mapping. After `process_batch` returns, callers can retrieve final results from `GET /api/jobs/{batch_id}/results`. Person 3 does not extract PDFs, anonymize resumes, or implement the adversarial scanner. Upstream code must call this boundary only after those checks succeed; this repository's current upload routes are still stubs and do not yet feed the Person 3 pipeline.

The M.10 boundary is the persisted `candidate_evaluations` result rows and the `/api/jobs/{batch_id}/results` response. Completed rows contain all six validated evaluation fields; pre-filtered and failed candidates remain terminal results without a Stage 2 evaluation. Automated scores are decision support, not hiring decisions.

Recovery marks `queued` and `extracting` jobs failed because their uploads and sanitized candidate inputs were not persisted. For `scoring` jobs, it resumes only the M.8 work whose rubric, Stage 1 scores, and promoted sanitized resumes were persisted; it retries those evaluations and finalizes the batch. A missing rubric, handoff, or candidate row is recorded as a failure. Recovery does not claim to reconstruct original uploads or re-run M.7 without its full input set.

Production deployments must provide PostgreSQL, a strong unique `JWT_SECRET`, and a valid `GEMINI_API_KEY` through a secret manager/environment; apply migrations before startup and back up the database. Do not commit `.env`, model weights, or real resume text. Only sanitized candidate text may cross into M.7/M.8; raw PDFs, anonymization, and adversarial scanning remain Person 2 responsibilities.
