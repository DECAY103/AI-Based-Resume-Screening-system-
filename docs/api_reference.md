# API Reference

Base URL: `https://<your-domain>/api`

All endpoints (except `/auth/login`) require `Authorization: Bearer <JWT>`.

---

## Auth — M.2

### `POST /auth/login`
Validate credentials, trigger 2FA.

**Body**
```json
{ "email": "string", "password": "string" }
```

**Response `200`**
```json
{ "message": "2FA code sent", "temp_token": "string" }
```

---

### `POST /auth/verify`
Verify 2FA code and receive a full JWT.

**Body**
```json
{ "temp_token": "string", "code": "string" }
```

**Response `200`**
```json
{ "access_token": "string", "token_type": "bearer", "role": "candidate|recruiter|admin" }
```

---

## Candidates — M.1 / M.3

### `POST /candidates/upload`
Single-resume upload (candidate role).

**Form Data**: `file` (PDF ≤ 5 MB), `job_id` (UUID string)

**Response `202`**
```json
{ "batch_id": "uuid", "status_url": "/api/jobs/{batch_id}/status" }
```

---

## Jobs — M.3 / M.9

### `POST /jobs/upload`
Batch ZIP upload (recruiter role).

**Form Data**: `file` (ZIP ≤ 50 MB), `rubric` (JSON string)

**Response `202`**
```json
{ "batch_id": "uuid", "status_url": "/api/jobs/{batch_id}/status" }
```

---

### `GET /jobs/{batch_id}/status`
Polling endpoint for batch progress.

**Response `200`**
```json
{
  "batch_id": "uuid",
  "status": "queued|extracting|scoring|completed|failed",
  "total_files": 0,
  "processed_files": 0,
  "failed_files": 0,
  "pre_filtered_count": 0,
  "progress_percentage": 0.0
}
```

---

### `GET /jobs/{batch_id}/results`
Ranked leaderboard for a completed batch (recruiter role).

**Response `200`**
```json
{
  "batch_id": "uuid",
  "results": [
    {
      "candidate_id": "uuid",
      "overall_score": 0.0,
      "skill_match_score": 0.0,
      "work_experience_score": 0.0,
      "matching_skills": [],
      "missing_skills": [],
      "verdict_summary": "string",
      "cosine_similarity_score": 0.0,
      "status": "completed|pre_filtered|failed"
    }
  ]
}
```

---

## Status Enum

| Value | Meaning |
|-------|---------|
| `queued` | Accepted, awaiting processing |
| `extracting` | Text extraction in progress |
| `scoring` | AI evaluation in progress |
| `pre_filtered` | Did not make Top-N cut in Stage 1 |
| `completed` | Stage 2 evaluation done |
| `failed` | Unrecoverable error (see `error_log`) |

## Person 2 → Person 3 application boundary

The upload endpoints above are currently stubs and do not run M.3–M.6 or
create a persisted batch. Once upstream processing is wired, it must call
`app.evaluation.stage1_pipeline.process_batch(batch_id, sanitized_candidate_texts)`
after validation, extraction, anonymization, and adversarial scanning have
succeeded. Before calling it, persist the batch and rubric with
`repository.create_batch_job(batch_id, total_files, rubric)`; `total_files`
must match the mapping size. `sanitized_candidate_texts` maps each UUID
`candidate_id` to sanitized resume text; the job rubric is persisted as
`batch_jobs.rubric`. Retrieve the final results from
`GET /api/jobs/{batch_id}/results` after processing completes. Person 3 does
not accept raw PDFs or implement PDF extraction, anonymization, or scanning.

The M.10 consumer contract is the persisted batch and candidate rows, plus the
completed-batch results response. Only promoted candidates receive a Stage 2
evaluation; pre-filtered and failed rows are terminal and are returned with
their status and cosine score but no LLM evaluation.
