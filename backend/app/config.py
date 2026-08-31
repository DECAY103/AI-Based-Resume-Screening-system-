"""
config.py — Application settings loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str

    # Auth
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Gemini (M.8)
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    # Pipeline config
    stage1_top_n: int = 10
    max_pdf_size_mb: int = 5
    max_zip_size_mb: int = 50
    max_zip_uncompressed_mb: int = 250

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
