# -*- coding: utf-8 -*-
"""账号接口：登录 / 退出 / 当前账号 / 改口令 / 会话 / 账号管理 / 登录审计。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Header, HTTPException, Query, Request

from .. import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else ""


@router.get("/status")
def status():
    """登录页用：系统有没有账号、首个管理员是否已初始化（不需要鉴权）。"""
    with auth.get_store().connect() as conn:
        total = conn.execute("SELECT count(*) FROM users").fetchone()[0]
        admins = conn.execute(
            "SELECT count(*) FROM users WHERE role='admin' AND enabled=1").fetchone()[0]
    return {"has_accounts": bool(total), "accounts": total, "admins": admins,
            "roles": [{"value": k, "label": v["label"]} for k, v in auth.ROLES.items()]}


@router.post("/login")
def login(request: Request, payload: dict = Body(...)):
    try:
        result = auth.login((payload or {}).get("username") or "",
                            (payload or {}).get("password") or "",
                            client_ip=_ip(request),
                            user_agent=request.headers.get("user-agent") or "",
                            remember=bool((payload or {}).get("remember")))
    except auth.AuthError as exc:
        raise HTTPException(exc.status, exc.message)
    result["overview"] = auth.overview(result["user"], client_ip=_ip(request))
    return result


@router.post("/logout")
def logout(request: Request):
    token = getattr(request.state, "token", "") or ""
    auth.logout(token, client_ip=_ip(request))
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, "未登录")
    return auth.overview(user, client_ip=_ip(request))


@router.post("/password")
def change_password(request: Request, payload: dict = Body(...)):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, "未登录")
    try:
        return {"ok": True, "result": auth.change_own_password(
            user["username"], (payload or {}).get("old_password") or "",
            (payload or {}).get("new_password") or "")}
    except auth.AuthError as exc:
        raise HTTPException(exc.status, exc.message)


@router.get("/sessions")
def sessions(request: Request, limit: int = Query(50, ge=1, le=200)):
    """我自己的活动会话；管理员可看全部（带 all=1）。"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, "未登录")
    username = "" if (user.get("is_admin") and request.query_params.get("all") == "1") \
        else user["username"]
    rows = auth.list_sessions(username=username, limit=limit)
    return {"sessions": rows, "total": len(rows), "limit": auth.MAX_ACTIVE_SESSIONS,
            "scope": "全部账号" if not username else "本账号"}


@router.delete("/sessions/{hint}")
def revoke_session(request: Request, hint: str):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, "未登录")
    if len(hint) < 6:
        raise HTTPException(400, "会话标识太短")
    removed = auth.revoke_session_by_hint(
        hint, operator=user["username"], allow_all=bool(user.get("is_admin")))
    if not removed:
        raise HTTPException(404, "没有匹配的活动会话")
    return {"ok": True, "removed": removed}


@router.get("/events")
def events(request: Request, limit: int = Query(100, ge=1, le=500),
           username: str = "", action: str = "", hours: int = Query(0, ge=0, le=24 * 365)):
    """登录审计：管理员看全部，普通账号只看自己。"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, "未登录")
    if not user.get("is_admin"):
        username = user["username"]
    return auth.events(limit=limit, username=username, action=action,
                       hours=hours)


# ------------------------------------------------------------------ 账号管理（仅管理员）
def _require_admin(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, "未登录")
    if not user.get("is_admin"):
        raise HTTPException(403, "只有超级管理员能管理账号")
    return user


@router.get("/users")
def list_users(request: Request):
    _require_admin(request)
    return {"users": auth.list_users(), "roles": [
        {"value": k, "label": v["label"]} for k, v in auth.ROLES.items()]}


@router.post("/users")
def create_user(request: Request, payload: dict = Body(...)):
    operator = _require_admin(request)["username"]
    try:
        user = auth.create_user((payload or {}).get("username") or "",
                                (payload or {}).get("password") or "",
                                display_name=(payload or {}).get("display_name") or "",
                                role=(payload or {}).get("role") or "viewer",
                                note=(payload or {}).get("note") or "",
                                operator=operator)
    except auth.AuthError as exc:
        raise HTTPException(exc.status, exc.message)
    return {"ok": True, "user": user}


@router.put("/users/{user_id}")
def update_user(request: Request, user_id: int, payload: dict = Body(...)):
    operator = _require_admin(request)["username"]
    try:
        return {"ok": True, "user": auth.update_user(user_id, payload or {}, operator=operator)}
    except auth.AuthError as exc:
        raise HTTPException(exc.status, exc.message)


@router.post("/users/{user_id}/password")
def reset_password(request: Request, user_id: int, payload: dict = Body(...)):
    operator = _require_admin(request)["username"]
    try:
        return {"ok": True, "result": auth.reset_password(
            user_id, (payload or {}).get("password") or "", operator=operator)}
    except auth.AuthError as exc:
        raise HTTPException(exc.status, exc.message)


@router.delete("/users/{user_id}")
def delete_user(request: Request, user_id: int):
    operator = _require_admin(request)["username"]
    try:
        return {"ok": True, "result": auth.delete_user(user_id, operator=operator)}
    except auth.AuthError as exc:
        raise HTTPException(exc.status, exc.message)