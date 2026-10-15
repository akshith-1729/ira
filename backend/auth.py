"""Password hashes, email checks, and session cookies. No demo accounts."""

import hashlib
import hmac
import os
import re
import secrets
import socket
from datetime import timedelta

from fastapi import HTTPException, Request, Response

_LOCAL = re.compile(r"^[a-z0-9](?:[a-z0-9._%+-]{0,62}[a-z0-9])?$")
_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_TLD = re.compile(r"^[a-z]{2,24}$")
_SCRYPT_N = 2**14
COOKIE = "ira_session"
SESSION_TTL = timedelta(days=14)


def email_problem(raw: str) -> str | None:
    """Why this address cannot be used, or None when the shape is acceptable."""
    email = (raw or "").strip().lower()
    if not email or "@" not in email or email.count("@") != 1:
        return "Enter a valid email."
    if len(email) > 254 or any(ord(ch) > 127 for ch in email):
        return "Enter a valid email."
    local, domain = email.split("@")
    if not _LOCAL.fullmatch(local) or ".." in local:
        return "Enter a valid email."
    labels = domain.split(".")
    if len(labels) < 2 or ".." in domain:
        return "Enter a valid email."
    if any(not _LABEL.fullmatch(label) for label in labels[:-1]):
        return "Enter a valid email."
    if not _TLD.fullmatch(labels[-1]):
        return "Enter a valid email."
    return None


def domain_accepts_mail(domain: str) -> bool:
    """The domain has to exist. A made-up host is not an email address."""
    try:
        socket.getaddrinfo(domain, None)
    except socket.gaierror:
        return False
    return True


def normalize_email(raw: str) -> str:
    problem = email_problem(raw)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    email = raw.strip().lower()
    if not domain_accepts_mail(email.split("@", 1)[1]):
        raise HTTPException(status_code=400, detail="That email domain could not be found.")
    return email


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def check_password(raw: str) -> str:
    password = raw or ""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Use at least 8 characters.")
    if len(password) > 200:
        raise HTTPException(status_code=400, detail="That password is too long.")
    return password


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = (stored or "").split("$")
        if scheme != "scrypt":
            return False
        check = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt_hex),
            n=_SCRYPT_N,
            r=8,
            p=1,
            dklen=32,
        )
        return hmac.compare_digest(check, bytes.fromhex(digest_hex))
    except (ValueError, TypeError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


def current_user(request: Request) -> dict | None:
    cookies = getattr(request, "cookies", None)
    token = cookies.get(COOKIE) if cookies is not None and hasattr(cookies, "get") else None
    if not isinstance(token, str) or not token:
        return None
    database = getattr(getattr(request, "app", None), "state", None)
    database = getattr(database, "db", None)
    if database is None or not getattr(database, "available", False):
        return None
    return database.user_for_session(hash_token(token))


def require_user(request: Request) -> dict:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user


def viewer_id(request: Request) -> str:
    user = current_user(request)
    return user["id"] if user else ""
