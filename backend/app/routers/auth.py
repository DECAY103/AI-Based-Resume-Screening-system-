"""Registration, password login, TOTP verification, JWT issuance, password reset, and activity logging."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import secrets
import smtplib
from email.mime.text import MIMEText

import pyotp
from fastapi import APIRouter, HTTPException, Request, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.models import (
    ActivityLogEntry, ActivityLogsResponse,
    LoginRequest, LoginResponse,
    PasswordResetConfirm, PasswordResetRequest, PasswordResetResponse,
    PasswordStrengthResponse,
    RegisterRequest, RegisterResponse,
    TokenResponse, VerifyRequest,
)
from app.persistence import repository
from app.security import CurrentUser, current_user
from fastapi import Depends

router = APIRouter()
# PBKDF2 avoids the passlib/bcrypt 5.x compatibility break and is available in
# Python's standard hashlib on every deployment target.
_passwords = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def _token(claims: dict, minutes: int) -> str:
    return jwt.encode({**claims, "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes)}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract client IP and User-Agent from the request."""
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)
    ua = request.headers.get("user-agent")
    return ip, ua


# ─── Password Strength (client-side check endpoint) ──────────────────────────

@router.post("/password-strength", response_model=PasswordStrengthResponse)
async def check_password_strength(body: dict) -> PasswordStrengthResponse:
    password = body.get("password", "")
    result = RegisterRequest.check_password_strength(password)
    return PasswordStrengthResponse(**result)


# ─── Register ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request) -> RegisterResponse:
    ip, ua = _client_info(request)

    # Enforce password strength server-side
    strength = RegisterRequest.check_password_strength(body.password)
    if not strength["is_acceptable"]:
        await repository.log_activity("register_failed_weak_password", email=body.email, detail=f"Password strength: {strength['level']}", ip_address=ip, user_agent=ua)
        raise HTTPException(status_code=400, detail=f"Password too weak ({strength['level']}). Must include uppercase, lowercase, digit, and special character.")

    secret = pyotp.random_base32()
    try:
        user = await repository.create_user(body.email, _passwords.hash(body.password), body.role, secret)
    except ValueError as exc:
        await repository.log_activity("register_failed_duplicate", email=body.email, detail=str(exc), ip_address=ip, user_agent=ua)
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await repository.log_activity("register_success", user_id=str(user["id"]), email=body.email, detail=f"Role: {body.role.value}", ip_address=ip, user_agent=ua)
    return RegisterResponse(message="Add this account to an authenticator app, then sign in.", otpauth_uri=pyotp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="Resume Screening"))


# ─── Login ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request) -> LoginResponse:
    ip, ua = _client_info(request)
    user = await repository.get_user_by_email(body.email)
    if not user or not _passwords.verify(body.password, user["password_hash"]):
        await repository.log_activity("login_failed", email=body.email, detail="Invalid email or password", ip_address=ip, user_agent=ua)
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    await repository.log_activity("login_password_ok", user_id=str(user["id"]), email=body.email, detail="Proceeding to 2FA", ip_address=ip, user_agent=ua)
    token = _token({"sub": str(user["id"]), "email": user["email"], "purpose": "2fa"}, settings.temp_token_expire_minutes)
    return LoginResponse(message="Enter the current code from your authenticator app.", temp_token=token)


# ─── 2FA Verification ────────────────────────────────────────────────────────

@router.post("/verify", response_model=TokenResponse)
async def verify_2fa(body: VerifyRequest, response: Response, request: Request) -> TokenResponse:
    ip, ua = _client_info(request)
    try:
        claims = jwt.decode(body.temp_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if claims.get("purpose") != "2fa": raise JWTError("wrong token")
    except JWTError as exc:
        await repository.log_activity("verify_failed_expired", detail="Verification session expired", ip_address=ip, user_agent=ua)
        raise HTTPException(status_code=401, detail="Verification session expired.") from exc
    user = await repository.get_user(claims["sub"])
    if not user or not pyotp.TOTP(user["totp_secret"]).verify(body.code, valid_window=1):
        await repository.log_activity("verify_failed_bad_code", user_id=claims["sub"], email=claims.get("email"), detail="Invalid authenticator code", ip_address=ip, user_agent=ua)
        raise HTTPException(status_code=401, detail="Invalid authenticator code.")

    # Update last login and get previous value
    previous_login = await repository.update_last_login(claims["sub"])
    await repository.log_activity("login_success", user_id=str(user["id"]), email=user["email"], detail=f"Previous login: {previous_login or 'first login'}", ip_address=ip, user_agent=ua)

    access = _token({"sub": str(user["id"]), "email": user["email"], "role": user["role"]}, settings.jwt_expire_minutes)
    response.set_cookie("access_token", access, httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=settings.jwt_expire_minutes * 60)
    return TokenResponse(access_token=access, role=user["role"], last_login_at=previous_login)


# ─── Password Reset — Request ────────────────────────────────────────────────

def _send_reset_email(to_email: str, reset_url: str) -> None:
    """Send password reset email via SMTP. Fails silently if SMTP is not configured."""
    if not settings.smtp_host:
        # In development, just log the URL
        import logging
        logging.getLogger(__name__).warning("SMTP not configured. Reset URL: %s", reset_url)
        return
    msg = MIMEText(
        f"Click the link below to reset your password. This link expires in {settings.password_reset_expire_minutes} minutes.\n\n{reset_url}\n\nIf you did not request this, ignore this email.",
        "plain",
    )
    msg["Subject"] = "Password Reset — Resume Screening"
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


@router.post("/forgot-password", response_model=PasswordResetResponse)
async def forgot_password(body: PasswordResetRequest, request: Request) -> PasswordResetResponse:
    ip, ua = _client_info(request)
    # Always return success to avoid email enumeration
    user = await repository.get_user_by_email(body.email)
    if user:
        token = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_expire_minutes)
        await repository.create_password_reset_token(str(user["id"]), token, expires_at)
        reset_url = f"{settings.frontend_url}/auth/reset-password?token={token}"
        try:
            _send_reset_email(body.email, reset_url)
        except Exception:
            pass  # Don't expose SMTP errors
        await repository.log_activity("password_reset_requested", user_id=str(user["id"]), email=body.email, ip_address=ip, user_agent=ua)
    else:
        await repository.log_activity("password_reset_unknown_email", email=body.email, ip_address=ip, user_agent=ua)
    return PasswordResetResponse(message="If an account with that email exists, a reset link has been sent.")


# ─── Password Reset — Confirm ────────────────────────────────────────────────

@router.post("/reset-password", response_model=PasswordResetResponse)
async def reset_password(body: PasswordResetConfirm, request: Request) -> PasswordResetResponse:
    ip, ua = _client_info(request)
    token_record = await repository.get_valid_reset_token(body.token)
    if not token_record:
        await repository.log_activity("password_reset_invalid_token", detail="Token invalid or expired", ip_address=ip, user_agent=ua)
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    # Enforce password strength
    strength = RegisterRequest.check_password_strength(body.new_password)
    if not strength["is_acceptable"]:
        raise HTTPException(status_code=400, detail=f"Password too weak ({strength['level']}). Must include uppercase, lowercase, digit, and special character.")

    user_id = str(token_record["user_id"])
    await repository.update_password(user_id, _passwords.hash(body.new_password))
    await repository.mark_reset_token_used(body.token)
    await repository.log_activity("password_reset_success", user_id=user_id, ip_address=ip, user_agent=ua)
    return PasswordResetResponse(message="Your password has been reset. You can now sign in with the new password.")


# ─── Activity Logs ────────────────────────────────────────────────────────────

@router.get("/activity-logs", response_model=ActivityLogsResponse)
async def get_activity_logs(user: CurrentUser = Depends(current_user)) -> ActivityLogsResponse:
    logs = await repository.get_activity_logs(user_id=user.user_id, limit=50)
    entries = [
        ActivityLogEntry(
            id=str(log["id"]),
            user_id=str(log["user_id"]) if log["user_id"] else None,
            email=log["email"],
            action=log["action"],
            detail=log["detail"],
            ip_address=log["ip_address"],
            created_at=log["created_at"].isoformat() if log["created_at"] else "",
        )
        for log in logs
    ]
    return ActivityLogsResponse(logs=entries)
