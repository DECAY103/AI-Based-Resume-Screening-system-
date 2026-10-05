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
│         │       → [M.7] Stage 1 Rank + persist            │  │
│         │       → [M.8] Gemini evaluator + validation     │  │
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

## Person 3 — Stage 1 and Stage 2 Handoff

After M.3–M.6 have produced validated, sanitized candidate text, the pipeline
calls `app.evaluation.stage1_pipeline.process_batch(batch_id, texts)` to run
M.7, M.8, and M.9. `rank_and_persist_batch` remains available as the Stage 1
only handoff when a caller needs that boundary separately.
The function loads the rubric stored on the batch and runs M.7 through
`asyncio.to_thread`, keeping sentence-transformers inference off the event
loop. The model is cached by the ranker and loaded once per process.

M.7 embeds the rubric and each sanitized résumé with `all-MiniLM-L6-v2` and
computes cosine similarity (dot product divided by the product of vector
lengths; zero vectors score 0). Candidates are sorted by descending
similarity, with candidate ID as a deterministic tie-breaker. A candidate is
promoted only when its rank is within configured `STAGE1_TOP_N` **and** its
score meets `STAGE1_SIMILARITY_THRESHOLD` (range −1 to 1). Every ranked score
is persisted. Promoted candidates enter `scoring`; all others enter
`pre_filtered`, and the batch pre-filter count is recomputed transactionally.

Only promoted sanitized résumé text is retained for the M.8 handoff; original
uploads and unsanitized extracted text are not stored. The orchestrator calls
`repository.get_stage2_candidates(batch_id)` and passes each sanitized resume
with the rubric to `app.evaluation.llm_evaluator.evaluate_candidate`. Each
response is parsed as JSON and validated as `UnifiedEvaluationSchema`.
Transient provider failures, malformed JSON, and schema failures are retried
using configured exponential backoff, subject to `STAGE2_TIMEOUT_SECONDS`.
After exhaustion, the candidate is
marked `failed`; provider exception contents are not written to logs or the
database. A candidate can only become `completed` when a validated evaluation
object is persisted. The repository validates the model before persistence,
and migration `003_validated_evaluation_guard.sql` enforces the same required
fields, types, and score ranges in PostgreSQL. Batch completion is guarded until
all candidate rows are terminal and every completed row contains a valid
evaluation. `pre_filtered` and `failed` candidates are terminal and do not need
an evaluation. The current upload routes still do not implement upstream
M.3–M.6 processing, so that upstream flow must call the Person 3 boundary only
with sanitized and adversarially scanned text.

For an existing database, apply `002_stage1_handoff.sql` after the initial
schema migration. It adds the nullable handoff text column without changing
existing rows; fresh databases also get the column from `001_initial.sql`.
Apply `003_validated_evaluation_guard.sql` after those migrations to enforce
the `UnifiedEvaluationSchema` contract for completed candidate rows.
The application and SQL migration agree on the canonical names `rubric`,
`sanitized_resume_text`, and `evaluation`. No project SRS/data dictionary,
`PROJECT_RULES.md`, or `DECISIONS.md` is included in this checkout, so the
checked-in migration and Pydantic/API models serve as the available schema
contract. There is no data rename or destructive migration.

## Fault Recovery

On startup, the FastAPI lifespan event scans PostgreSQL for records in `queued`, `extracting`, or `scoring` states. Queued and extracting work is marked `failed` because its uploaded files and sanitized candidate inputs were not persisted. A scoring batch already has M.7 scores and promoted sanitized text in PostgreSQL, so recovery retries only those Stage 2 evaluations, validates and persists them, and completes the batch when every source file has a terminal row. A missing rubric, handoff, or candidate row is recorded as a failure. Recovery does not claim to reconstruct original uploads or rerun M.7 without its full input set.

## Security Constraints

- JWT tokens issued on login; 2FA code validated before token grant.
- Role enum: `candidate | recruiter | admin` enforced at the route level.
- Person 2 must reject adversarial/prompt-injection content before calling the Person 3 boundary. The current upload routes do not yet wire M.3–M.6, and Person 3 does not claim to anonymize or scan text itself.
- Automated scores are **advisory only** — human recruiters make final decisions.
