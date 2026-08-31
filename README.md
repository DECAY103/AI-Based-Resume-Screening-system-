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
        │  (Top-N promoted)
        ▼
[M.8] Stage 2 — Gemini Flash structured evaluation
        │
        ▼
[M.9] Persist to PostgreSQL
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

Status flow: `queued → extracting → scoring → pre_filtered → completed | failed`
