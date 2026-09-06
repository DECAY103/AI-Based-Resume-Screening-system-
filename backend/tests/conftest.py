import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/resume_screening_test")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
