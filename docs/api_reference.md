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
      "status": "completed|pre_filtered"
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
