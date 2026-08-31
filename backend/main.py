"""
main.py — FastAPI application entry point.

Startup lifecycle (lifespan):
  1. Initialise the asyncpg connection pool.
  2. Run orphan-job recovery (M.9 — Person 3).
  3. Yield control to FastAPI.
  4. On shutdown: close the pool.

Run locally:
    uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.database import init_db, close_db
from app.persistence.recovery import recover_orphaned_jobs
from app.routers import auth, candidates, jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
    await init_db()
    await recover_orphaned_jobs()   # M.9 — Person 3
    yield
    # ── Shutdown ───────────────────────────────────────────────────────────────
    await close_db()


app = FastAPI(
    title="AI Resume Screening API",
    description="Cloud-native resume screening engine with two-stage AI evaluation.",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router,       prefix="/api/auth",       tags=["auth"])
app.include_router(candidates.router, prefix="/api/candidates", tags=["candidates"])
app.include_router(jobs.router,       prefix="/api/jobs",       tags=["jobs"])


@app.get("/api/health", tags=["health"])
async def health_check():
    """Simple liveness probe."""
    return {"status": "ok"}
