from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import StudentProfile

bearer_scheme = HTTPBearer(auto_error=False)


def issue_session_token(student_id: str, lifetime_seconds: int = 60 * 60 * 24 * 30) -> str:
    secret = get_settings().otp_signing_secret
    if len(secret) < 32:
        raise HTTPException(503, "Set OTP_SIGNING_SECRET to a random value of at least 32 characters in .env.")
    payload = json.dumps({"sub": student_id, "exp": int(time.time()) + lifetime_seconds}, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(secret.encode(), encoded, hashlib.sha256).digest()
    return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def decode_session_token(token: str) -> dict[str, object]:
    secret = get_settings().otp_signing_secret
    try:
        payload_part, signature_part = token.split(".", 1)
        signature = base64.urlsafe_b64decode(signature_part + "=" * (-len(signature_part) % 4))
        expected = hmac.new(secret.encode(), payload_part.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        payload_bytes = base64.urlsafe_b64decode(payload_part + "=" * (-len(payload_part) % 4))
        payload = json.loads(payload_bytes)
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("Expired token")
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(401, "Prototype profile session expired. Reload the app to continue.") from exc


def get_current_student(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> StudentProfile:
    if credentials is None:
        raise HTTPException(401, "Create a prototype profile to continue.")
    payload = decode_session_token(credentials.credentials)
    student = db.get(StudentProfile, str(payload.get("sub", "")))
    if student is None:
        raise HTTPException(401, "Student profile was not found. Sign in again.")
    return student


def require_matching_student(student_id: str, current: StudentProfile = Depends(get_current_student)) -> StudentProfile:
    if current.student_id != student_id:
        raise HTTPException(403, "You can only access your own student profile.")
    return current
