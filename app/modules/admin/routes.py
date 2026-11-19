"""Concat Web administration and verified Scene SSO endpoints.

Scene remains the authority for user accounts and roles; this app controls
only Concat grants, app configuration and its own revocable sessions.
"""
from pathlib import Path
import os
import secrets
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, StrictBool, conint

from app.auth import Principal, admin_principal, current_principal
from app.modules.admin.security import (
    COOKIE, STATE_COOKIE, _safe_return_path, get_security, require_csrf,
    SecurityUnavailable,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
PRIVATE = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"}


def _local_only(request: Request):
    if os.environ.get("CONCAT_AUTH_MODE", "scene").strip() != "local":
        raise HTTPException(404, "Local login not available")
    service = get_security(request)
    if not getattr(service, "is_local", False):
        raise HTTPException(503, "Local authentication unavailable")
    return service


def _same_origin(request: Request, allowed: str) -> None:
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    if origin:
        if origin.rstrip("/") != allowed:
            raise HTTPException(403, "Login origin rejected")
    elif referer:
        parsed = urlsplit(referer)
        if parsed.scheme + "://" + parsed.netloc != allowed:
            raise HTTPException(403, "Login origin rejected")
    else:
        raise HTTPException(403, "Login origin required")


@router.get("/auth/login", response_class=HTMLResponse)
async def local_login_page(request: Request):
    _local_only(request)
    return templates.TemplateResponse(
        request=request, name="login.html", context={},
        headers=PRIVATE,
    )


@router.post("/auth/login")
async def local_login_post(request: Request):
    service = _local_only(request)
    _same_origin(request, service.web_origin)
    if not request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
        raise HTTPException(415, "Form submission required")
    form = await request.form()
    username, password = form.get("username"), form.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        raise HTTPException(401, "Invalid username or password")
    token, max_age = service.login(username, password, request)
    service.revoke_cookie(request)  # rotate prior browser session
    response = RedirectResponse("/dashboard", status_code=303, headers=PRIVATE)
    response.set_cookie(COOKIE, token, max_age=max_age, secure=True,
                        httponly=True, samesite="lax", path="/")
    return response


@router.get("/auth/scene/start")
async def scene_login(request: Request, next: str = "/dashboard"):
    if os.environ.get("CONCAT_AUTH_MODE", "scene").strip() == "local":
        raise HTTPException(404, "Scene login disabled in personal mode")
    service = get_security(request)
    state = secrets.token_urlsafe(32)
    # The upstream issuer MUST require a real active Scene session and use
    # its own pinned callback allowlist, never arbitrary redirect_uri values.
    params = urlencode({
        "client_id": "concat-web",
        "state": state,
        "redirect_uri": service.web_origin + "/auth/scene/callback",
    })
    response = RedirectResponse(
        service.scene_origin + "/concat-sso/authorize?" + params,
        status_code=303, headers=PRIVATE,
    )
    response.set_cookie(STATE_COOKIE, state, max_age=180, secure=True,
                        httponly=True, samesite="lax", path="/")
    return response


@router.get("/auth/scene/callback")
async def scene_callback(request: Request, ticket: str = "", state: str = ""):
    if os.environ.get("CONCAT_AUTH_MODE", "scene").strip() == "local":
        raise HTTPException(404, "Scene login disabled in personal mode")
    service = get_security(request)
    cookie_state = request.cookies.get(STATE_COOKIE, "")
    if not cookie_state or len(cookie_state) < 32 or len(state) > 200 or not secrets.compare_digest(cookie_state, state):
        raise HTTPException(401, "Invalid Scene SSO state")
    try:
        username, sid_hash, jti_hash = service.validate_ticket(ticket, state)
        token, _, max_age = service.create_session(username, sid_hash, jti_hash)
    except SecurityUnavailable as exc:
        raise HTTPException(503, "Scene SSO session verification unavailable") from exc
    service.revoke_cookie(request)  # rotate any prior Concat browser session
    response = RedirectResponse("/dashboard", status_code=303, headers=PRIVATE)
    response.delete_cookie(STATE_COOKIE, path="/", secure=True, httponly=True)
    response.set_cookie(COOKIE, token, max_age=max_age, secure=True,
                        httponly=True, samesite="lax", path="/")
    return response


@router.get("/api/v1/auth/csrf")
async def csrf_token(request: Request, _: Principal = Depends(current_principal)):
    csrf = get_security(request).csrf_token(request)
    if not csrf:
        raise HTTPException(401, "Verified browser session required")
    return JSONResponse({"csrf_token": csrf}, headers=PRIVATE)


@router.post("/auth/logout", dependencies=[Depends(require_csrf)])
async def logout(request: Request, _: Principal = Depends(current_principal)):
    get_security(request).revoke_cookie(request)
    response = RedirectResponse("/auth/login" if getattr(get_security(request), "is_local", False) else "/auth/scene/start",
                                status_code=303, headers=PRIVATE)
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True)
    return response


@router.get("/admin", response_class=HTMLResponse)
async def admin(request: Request, principal: Principal = Depends(admin_principal)):
    return templates.TemplateResponse(
        request=request, name="admin.html",
        context={"principal": principal, "local_mode": getattr(get_security(request), "is_local", False)}, headers=PRIVATE,
    )


@router.get("/api/v1/admin/users")
async def users(request: Request, _: Principal = Depends(admin_principal)):
    return JSONResponse({"users": get_security(request).users()}, headers=PRIVATE)


class GrantBody(BaseModel):
    concat_granted: StrictBool

    model_config = {"extra": "forbid"}


@router.post("/api/v1/admin/users/{username}/access", dependencies=[Depends(require_csrf)])
async def user_access(username: str, body: GrantBody, request: Request,
                      principal: Principal = Depends(admin_principal)):
    service = get_security(request)
    service.grant(principal.username, username, body.concat_granted)
    return JSONResponse({"ok": True}, headers=PRIVATE)


@router.post("/api/v1/admin/users/{username}/revoke-sessions", dependencies=[Depends(require_csrf)])
async def revoke_user_sessions(username: str, request: Request,
                               principal: Principal = Depends(admin_principal)):
    count = get_security(request).revoke_user(principal.username, username)
    return JSONResponse({"ok": True, "revoked": count}, headers=PRIVATE)


@router.get("/api/v1/admin/config")
async def config(request: Request, _: Principal = Depends(admin_principal)):
    service = get_security(request)
    return JSONResponse({"config": service.config() if getattr(service, "is_local", False) else service._config(),
                         "scene_origin": getattr(service, "scene_origin", None),
                         "scene_identity": "not-used" if getattr(service, "is_local", False) else "read-only",
                         "secrets_exposed": False}, headers=PRIVATE)


class ConfigBody(BaseModel):
    maintenance_mode: StrictBool | None = None
    session_max_minutes: conint(strict=True, ge=15, le=480) | None = None

    model_config = {"extra": "forbid"}


@router.post("/api/v1/admin/config", dependencies=[Depends(require_csrf)])
async def save_config(body: ConfigBody, request: Request, principal: Principal = Depends(admin_principal)):
    values = body.model_dump(exclude_unset=True)
    return JSONResponse({"config": get_security(request).update_config(principal.username, values)}, headers=PRIVATE)


@router.get("/api/v1/admin/audit")
async def audit(request: Request, _: Principal = Depends(admin_principal)):
    return JSONResponse({"events": get_security(request).audit()}, headers=PRIVATE)
