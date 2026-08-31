"""
routers/auth.py — JWT + 2FA authentication endpoints.
Owner: Person 1 (M.2)

Endpoints:
  POST /api/auth/login   — validate credentials, trigger 2FA
  POST /api/auth/verify  — validate 2FA code, issue JWT
"""
from fastapi import APIRouter, HTTPException, status

from app.models import LoginRequest, LoginResponse, VerifyRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(body: LoginRequest) -> LoginResponse:
    """
    Validate email/password credentials.
    On success: generate a short-lived temp_token and send a TOTP 2FA code.

    TODO (Person 1 — M.2):
      - Query the users table for the given email.
      - Verify the hashed password with passlib.
      - Generate a TOTP code with pyotp and send it via email/SMS.
      - Return a signed temp_token (short expiry) containing the user_id.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="[M.2] Login not yet implemented.",
    )


@router.post("/verify", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def verify_2fa(body: VerifyRequest) -> TokenResponse:
    """
    Validate the TOTP 2FA code and exchange temp_token for a full JWT.

    TODO (Person 1 — M.2):
      - Decode and validate the temp_token.
      - Verify the TOTP code is correct and not expired.
      - Issue a long-lived JWT containing user_id and role.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="[M.2] 2FA verify not yet implemented.",
    )
