"""Register, sign in, and the signed-in shelf."""

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from auth import (
    check_password,
    clear_session_cookie,
    current_user,
    hash_password,
    hash_token,
    new_code,
    new_token,
    normalize_email,
    require_user,
    set_session_cookie,
    verify_password,
)
from mail import send_code

router = APIRouter()


class AuthIn(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class EmailIn(BaseModel):
    email: str = Field(min_length=3)


class VerifyIn(BaseModel):
    email: str = Field(min_length=3)
    code: str = Field(min_length=6, max_length=6)


class ProfileIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1)


def _public(user: dict, counts: dict | None = None) -> dict:
    counts = counts or {}
    created = user.get("created_at")
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user.get("display_name") or "",
        "verified": user.get("email_verified_at") is not None,
        "created_at": created.isoformat() if hasattr(created, "isoformat") else created,
        "papers": counts.get("papers", 0),
        "analyses": counts.get("analyses", 0),
    }


def _issue(response: Response, database, user_id: str) -> str:
    token = new_token()
    database.create_session(user_id, hash_token(token))
    set_session_cookie(response, token)
    return token


def _deliver_code(request: Request, user: dict) -> dict:
    code = new_code()
    request.app.state.db.save_email_code(user["id"], hash_token(code))
    sent = send_code(request.app.state.settings, user["email"], code)
    body = {"email": user["email"], "verified": False, "delivery": "email" if sent else "screen"}
    if not sent:
        body["code"] = code
    return body


@router.post("/auth/register")
def register(body: AuthIn, request: Request):
    if not request.app.state.db.available:
        raise HTTPException(status_code=503, detail="Jobs are offline.")
    email = normalize_email(body.email)
    password = check_password(body.password)
    try:
        user = request.app.state.db.create_user(email, hash_password(password))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="An account with that email already exists.") from exc
    payload = _deliver_code(request, user)
    payload["id"] = user["id"]
    return payload


@router.post("/auth/verify")
def verify_email(body: VerifyIn, request: Request, response: Response):
    if not request.app.state.db.available:
        raise HTTPException(status_code=503, detail="Jobs are offline.")
    email = normalize_email(body.email)
    user = request.app.state.db.user_by_email(email)
    code = (body.code or "").strip()
    if (
        user is None
        or user.get("email_verified_at")
        or not code.isdigit()
        or not request.app.state.db.email_code_matches(user["id"], hash_token(code))
    ):
        raise HTTPException(status_code=400, detail="That code is wrong or it has expired.")
    request.app.state.db.mark_email_verified(user["id"])
    user = request.app.state.db.user_by_email(email)
    _issue(response, request.app.state.db, user["id"])
    counts = request.app.state.db.account_counts(user["id"])
    return _public(user, counts)


@router.post("/auth/verify/send")
def resend_code(body: EmailIn, request: Request):
    if not request.app.state.db.available:
        raise HTTPException(status_code=503, detail="Jobs are offline.")
    email = normalize_email(body.email)
    user = request.app.state.db.user_by_email(email)
    if user is None or user.get("email_verified_at"):
        raise HTTPException(status_code=400, detail="That account is not waiting for a code.")
    return _deliver_code(request, user)


@router.post("/auth/login")
def login(body: AuthIn, request: Request, response: Response):
    if not request.app.state.db.available:
        raise HTTPException(status_code=503, detail="Jobs are offline.")
    email = normalize_email(body.email)
    password = body.password or ""
    user = request.app.state.db.user_by_email(email)
    if user is None or not user.get("password_hash") or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is wrong.")
    if user.get("email_verified_at") is None:
        raise HTTPException(status_code=403, detail="Confirm your email before signing in.")
    _issue(response, request.app.state.db, user["id"])
    counts = request.app.state.db.account_counts(user["id"])
    return _public(user, counts)


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    cookies = request.cookies
    token = cookies.get("ira_session") if cookies is not None else None
    if isinstance(token, str) and token and request.app.state.db.available:
        request.app.state.db.delete_session(hash_token(token))
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request):
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    counts = request.app.state.db.account_counts(user["id"])
    return _public(user, counts)


@router.patch("/auth/profile")
def update_profile(body: ProfileIn, request: Request):
    user = require_user(request)
    name = " ".join(body.display_name.split())
    if not name or len(name) > 80:
        raise HTTPException(status_code=400, detail="Enter the name you want on your profile.")
    request.app.state.db.set_display_name(user["id"], name)
    fresh = request.app.state.db.user_by_email(user["email"])
    return _public(fresh, request.app.state.db.account_counts(user["id"]))


@router.post("/auth/password")
def change_password(body: PasswordIn, request: Request):
    user = require_user(request)
    stored = request.app.state.db.user_by_email(user["email"])
    if stored is None or not verify_password(body.current_password, stored.get("password_hash") or ""):
        raise HTTPException(status_code=400, detail="The current password is wrong.")
    new_password = check_password(body.new_password)
    if new_password == body.current_password:
        raise HTTPException(status_code=400, detail="Choose a different password.")
    request.app.state.db.set_password_hash(user["id"], hash_password(new_password))
    return {"ok": True}


@router.get("/library")
def library(request: Request):
    user = require_user(request)
    database = request.app.state.db
    return {"papers": database.library_for(user["id"]), "jobs": database.jobs_for(user["id"])}


@router.delete("/library/{paper_id}")
def remove_from_library(paper_id: str, request: Request):
    user = require_user(request)
    database = request.app.state.db
    row = database.library_row(user["id"], paper_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That paper is not on your shelf.")
    if row["private"]:
        if not request.app.state.graph.available:
            raise HTTPException(status_code=503, detail="The library is offline.")
        removed = request.app.state.store.delete_private_paper(paper_id, owner=user["id"])
        if not removed:
            raise HTTPException(status_code=404, detail="That paper is not on your shelf.")
    database.remove_library(user["id"], paper_id)
    return {"removed": paper_id}
