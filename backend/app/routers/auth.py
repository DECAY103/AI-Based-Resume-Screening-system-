"""Registration, password login, TOTP verification, and JWT issuance."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import pyotp
from fastapi import APIRouter, HTTPException, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings
from app.models import LoginRequest, LoginResponse, RegisterRequest, RegisterResponse, TokenResponse, VerifyRequest
from app.persistence import repository

router = APIRouter()
# PBKDF2 avoids the passlib/bcrypt 5.x compatibility break and is available in
# Python's standard hashlib on every deployment target.
_passwords = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def _token(claims: dict, minutes: int) -> str:
    return jwt.encode({**claims, "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes)}, settings.jwt_secret, algorithm=settings.jwt_algorithm)

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest) -> RegisterResponse:
    secret = pyotp.random_base32()
    try:
        user = await repository.create_user(body.email, _passwords.hash(body.password), body.role, secret)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RegisterResponse(message="Add this account to an authenticator app, then sign in.", otpauth_uri=pyotp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="Resume Screening"))

@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    user = await repository.get_user_by_email(body.email)
    if not user or not _passwords.verify(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = _token({"sub": str(user["id"]), "email": user["email"], "purpose": "2fa"}, settings.temp_token_expire_minutes)
    return LoginResponse(message="Enter the current code from your authenticator app.", temp_token=token)

@router.post("/verify", response_model=TokenResponse)
async def verify_2fa(body: VerifyRequest, response: Response) -> TokenResponse:
    try:
        claims = jwt.decode(body.temp_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if claims.get("purpose") != "2fa": raise JWTError("wrong token")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Verification session expired.") from exc
    user = await repository.get_user(claims["sub"])
    if not user or not pyotp.TOTP(user["totp_secret"]).verify(body.code, valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid authenticator code.")
    access = _token({"sub": str(user["id"]), "email": user["email"], "role": user["role"]}, settings.jwt_expire_minutes)
    response.set_cookie("access_token", access, httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=settings.jwt_expire_minutes * 60)
    return TokenResponse(access_token=access, role=user["role"])
