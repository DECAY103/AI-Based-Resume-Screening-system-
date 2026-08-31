# Repo Skeleton Tasks

## Root
- [ ] README.md
- [ ] .gitignore
- [ ] .github/CODEOWNERS

## Docs
- [ ] docs/architecture.md
- [ ] docs/api_reference.md

## Frontend (Person 1)
- [ ] frontend/package.json
- [ ] frontend/next.config.js
- [ ] frontend/.env.local.example
- [ ] frontend/public/.gitkeep
- [ ] frontend/src/app/layout.tsx
- [ ] frontend/src/app/page.tsx
- [ ] frontend/src/app/candidate/page.tsx
- [ ] frontend/src/app/recruiter/page.tsx
- [ ] frontend/src/app/recruiter/leaderboard/page.tsx
- [ ] frontend/src/app/auth/login/page.tsx
- [ ] frontend/src/app/auth/verify/page.tsx
- [ ] frontend/src/components/UploadForm.tsx
- [ ] frontend/src/components/StatusPoller.tsx
- [ ] frontend/src/components/Leaderboard.tsx
- [ ] frontend/src/lib/api.ts
- [ ] frontend/src/middleware.ts

## Backend — Shared
- [ ] backend/requirements.txt
- [ ] backend/.env.example
- [ ] backend/main.py
- [ ] backend/app/__init__.py
- [ ] backend/app/config.py
- [ ] backend/app/database.py
- [ ] backend/app/models.py
- [ ] backend/app/routers/__init__.py
- [ ] backend/app/routers/auth.py
- [ ] backend/app/routers/candidates.py
- [ ] backend/app/routers/jobs.py

## Backend — Person 2 (Ingestion & Sanitisation)
- [ ] backend/app/ingestion/__init__.py
- [ ] backend/app/ingestion/validator.py
- [ ] backend/app/ingestion/extractor.py
- [ ] backend/app/sanitisation/__init__.py
- [ ] backend/app/sanitisation/anonymiser.py
- [ ] backend/app/sanitisation/adversarial.py

## Backend — Person 3 (AI Eval & Persistence)
- [ ] backend/app/evaluation/__init__.py
- [ ] backend/app/evaluation/semantic_ranker.py
- [ ] backend/app/evaluation/llm_evaluator.py
- [ ] backend/app/persistence/__init__.py
- [ ] backend/app/persistence/repository.py
- [ ] backend/app/persistence/recovery.py
- [ ] backend/app/persistence/migrations/001_initial.sql
