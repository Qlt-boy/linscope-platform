# -*- coding: utf-8 -*-
"""远程登录接口：设备与凭据管理、连通性测试、WebSocket 控制台、会话留痕。"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import threading
from urllib.parse import quote

from fastapi import (APIRouter, Body, HTTPException, Query, Request, WebSocket,
                     WebSocketDisconnect)
from fastapi.responses import Response, StreamingResponse

from .. import auth, remote
from ..store import get_store

router = APIRouter(prefix="/api/remote", tags=["remote"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else ""


# ------------------------------------------------------------------ 概览 / 策略
@router.get("/overview")
def overview():
    """远程登录页数据：可登录的网络设备 + 凭据状态 + 会话统计 + 策略 + 依赖自检。"""
    return remote.remote_overview()


@router.get("/policy")
def get_policy():
    return {"policy": remote.policy(), "defaults": remote.DEFAULT_POLICY,
            "modes": [
                {"value": "confirm", "label": "变更类命令需人工确认（推荐）"},
                {"value": "block", "label": "只放行查看类命令（严格）"},
                {"value": "off", "label": "不做命令拦截（仅留痕）"},
            ]}


@router.post("/policy")
def post_policy(payload: dict = Body(...)):
    return {"ok": True, "policy": remote.save_policy(payload or {})}


@router.post("/check")
def check_command(payload: dict = Body(...)):
    """试跑一条命令，看看会被放行 / 需确认 / 拦截（改策略前先自测）。"""
    return remote.check_command((payload or {}).get("command") or "")


# ------------------------------------------------------------------ 凭据
@router.get("/credentials")
def list_credentials():
    return {"credentials": remote.credentials_list()}


@router.get("/credentials/{ip}")
def get_credential(ip: str):
    cred = remote.credential_get(ip)
    if not cred:
        return {"ip": ip, "configured": False}
    return {"ip": ip, "configured": True,
            "username": cred.get("username"), "port": cred.get("port"),
            "auth": cred.get("auth"), "note": cred.get("note") or "",
            "has_secret": bool(cred.get("secret_enc")),
            "has_key": bool(cred.get("key_enc")),
            "host_key_fp": cred.get("host_key_fp") or "",
            "host_key_at": cred.get("host_key_at") or "",
            "updated_at": cred.get("updated_at") or ""}


@router.put("/credentials/{ip}")
def put_credential(ip: str, request: Request, payload: dict = Body(...)):
    user = request.state.user
    try:
        saved = remote.credential_save(ip, payload or {}, operator=user["username"])
        auth.log_event(ip, "credential_update", "更新设备登录凭据",
                       operator=user["username"], target_type="device")
        return {"ok": True, "credential": saved}
    except remote.RemoteError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/credentials/{ip}")
def delete_credential(ip: str, request: Request):
    removed = remote.credential_delete(ip)
    if not removed:
        raise HTTPException(404, "该设备没有配置凭据")
    auth.log_event(ip, "credential_delete", "删除设备登录凭据",
                   operator=request.state.user["username"], target_type="device")
    return {"ok": True, "ip": ip}


@router.post("/host-key/{ip}/reset")
def reset_host_key(ip: str, request: Request):
    """管理员核实设备更换后，清除已固定的 SSH 主机指纹。"""
    user = request.state.user
    if not user.get("is_admin"):
        raise HTTPException(403, "只有超级管理员能重置 SSH 主机指纹")
    with get_store().connect() as conn:
        cur = conn.execute(
            "UPDATE credentials SET host_key_type='', host_key_b64='', host_key_fp='',"
            " host_key_at='' WHERE ip=?", (ip,))
    if not cur.rowcount:
        raise HTTPException(404, "该设备没有配置凭据")
    auth.log_event(ip, "ssh_host_key_reset", "管理员清除已固定的 SSH 主机指纹",
                   operator=user["username"], target_type="device")
    return {"ok": True, "ip": ip}


@router.post("/test")
def test_target(payload: dict = Body(...)):
    """测试待采集区或台账设备的 SSH 连接；支持测试尚未保存的凭据。"""
    payload = payload or {}
    ip = payload.get("ip") or ""
    if not ip:
        raise HTTPException(400, "缺少 ip")
    if not get_store().device_get(ip):
        raise HTTPException(403, "%s 不在待采集区，请先新增或导入设备" % ip)
    if any(key in payload for key in ("username", "password", "private_key", "port", "auth")):
        return remote.test_connection_candidate(ip, payload)
    return remote.test_connection(ip)


# ------------------------------------------------------------------ 会话留痕
@router.get("/sessions")
def list_sessions(limit: int = Query(50, ge=1, le=500), ip: str = ""):
    return remote.sessions(limit=limit, ip=ip)


@router.get("/sessions/{session_id}/commands")
def list_commands(session_id: int, limit: int = Query(500, ge=1, le=2000)):
    return remote.session_commands(session_id, limit)


# ------------------------------------------------------------------ SFTP 文件管理
def _sftp_user(request: Request) -> dict:
    user = getattr(request.state, "user", None) or {}
    if not user or not auth.permissions_of(user).get("remote"):
        raise HTTPException(403, "当前角色没有远程文件管理权限")
    return user


def _raise_sftp(exc: Exception):
    if isinstance(exc, remote.RemoteError):
        raise HTTPException(400, str(exc))
    raise HTTPException(500, "SFTP 操作失败：%s" % exc)


@router.get("/sftp/list")
def sftp_list(request: Request, ip: str = Query(...), path: str = ""):
    user = _sftp_user(request)
    try:
        return remote.sftp_list(ip, path, operator=user.get("username") or "")
    except Exception as exc:                           # noqa: BLE001
        _raise_sftp(exc)


@router.get("/sftp/download")
def sftp_download(request: Request, ip: str = Query(...), path: str = Query(...)):
    user = _sftp_user(request)
    try:
        item = remote.sftp_download(
            ip, path, operator=user.get("username") or "",
            client_ip=_client_ip(request))
    except Exception as exc:                           # noqa: BLE001
        _raise_sftp(exc)
    filename = quote(item.get("name") or "download.bin")
    media = mimetypes.guess_type(item.get("name") or "")[0] or "application/octet-stream"
    return StreamingResponse(item["chunks"](), media_type=media, headers={
        "Content-Disposition": "attachment; filename*=UTF-8''%s" % filename,
        "X-File-Size": str(item.get("size") or 0),
        "Access-Control-Expose-Headers": "Content-Disposition, X-File-Size",
    })


@router.post("/sftp/upload")
async def sftp_upload(request: Request, ip: str = Query(...), path: str = Query("."),
                      name: str = Query(...)):
    user = _sftp_user(request)
    data = await request.body()
    if len(data) > 128 * 1024 * 1024:
        raise HTTPException(413, "单次上传不能超过 128MB")
    try:
        return remote.sftp_upload(
            ip, path, name, data, operator=user.get("username") or "",
            client_ip=_client_ip(request))
    except Exception as exc:                           # noqa: BLE001
        _raise_sftp(exc)


@router.post("/sftp/mkdir")
def sftp_mkdir(request: Request, payload: dict = Body(...)):
    user = _sftp_user(request)
    try:
        return remote.sftp_mkdir(
            (payload or {}).get("ip") or "", (payload or {}).get("path") or ".",
            (payload or {}).get("name") or "", operator=user.get("username") or "",
            client_ip=_client_ip(request))
    except Exception as exc:                           # noqa: BLE001
        _raise_sftp(exc)


@router.post("/sftp/rename")
def sftp_rename(request: Request, payload: dict = Body(...)):
    user = _sftp_user(request)
    try:
        return remote.sftp_rename(
            (payload or {}).get("ip") or "", (payload or {}).get("path") or "",
            (payload or {}).get("new_name") or "", operator=user.get("username") or "",
            client_ip=_client_ip(request))
    except Exception as exc:                           # noqa: BLE001
        _raise_sftp(exc)


@router.delete("/sftp/item")
def sftp_delete(request: Request, ip: str = Query(...), path: str = Query(...)):
    user = _sftp_user(request)
    try:
        return remote.sftp_delete(
            ip, path, operator=user.get("username") or "",
            client_ip=_client_ip(request))
    except Exception as exc:                           # noqa: BLE001
        _raise_sftp(exc)

# ------------------------------------------------------------------ 控制台（WebSocket）
@router.websocket("/session/{ip}")
async def ws_session(websocket: WebSocket, ip: str):
    """浏览器 xterm.js ↔ 后端 ↔ 设备 SSH shell 的实时通道。

    只允许连本平台台账里的设备；每条命令、每次拦截都写库留痕。
    """
    await websocket.accept()
    # WebSocket 不走 HTTP 中间件，这里自己校验令牌（浏览器 WS 不能带自定义头，用 ?token=）
    token = (websocket.query_params.get("token") or "").strip()
    user = auth.resolve(token) if token else None
    devices, _, _ = remote.devices_view_safe()
    device = next((d for d in devices if d["ip"] == ip), None)
    operator = (user or {}).get("username") or websocket.query_params.get("operator") or "匿名"

    async def fail(reason: str):
        await websocket.send_text(json.dumps(
            {"type": "notice", "level": "error", "text": reason}, ensure_ascii=False))
        await websocket.send_text(json.dumps(
            {"type": "closed", "reason": reason}, ensure_ascii=False))
        await websocket.close()

    if not user:
        await fail("未登录或会话已过期：请重新登录后再开控制台")
        return
    if not auth.permissions_of(user).get("remote"):
        await fail("当前角色（%s）没有远程登录权限" % auth.ROLE_LABELS.get(user.get("role"), ""))
        return
    if device is None:
        await fail("%s 不在设备台账里，拒绝连接（请先在设备清单新增该设备）" % ip)
        return
    if not remote.credential_get(ip):
        await fail("设备 %s 还没有配置登录凭据，请先在设备列表点「配置凭据」" % ip)
        return

    forwarded = websocket.headers.get("x-forwarded-for") or ""
    client_ip = (forwarded.split(",")[0].strip() if forwarded
                 else (websocket.headers.get("x-real-ip") or "").strip()
                 or (websocket.client.host if websocket.client else ""))
    loop = asyncio.get_running_loop()
    outbox: asyncio.Queue = asyncio.Queue()

    def emit(event: dict) -> None:
        try:
            loop.call_soon_threadsafe(outbox.put_nowait, event)
        except RuntimeError:
            pass

    full_mode = (websocket.query_params.get("mode") or "").lower() in ("full", "admin")
    allow_full = full_mode and auth.permissions_of(user).get("remote_full")
    session = remote.RemoteSession(ip, device.get("name") or "", operator,
                                  client_ip, emit=emit,
                                  unrestricted=bool(allow_full))
    thread = threading.Thread(target=session.run, daemon=True)
    thread.start()

    async def pump() -> None:
        while True:
            event = await outbox.get()
            await websocket.send_text(json.dumps(event, ensure_ascii=False))

    pump_task = asyncio.create_task(pump())
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = message.get("type")
            if kind == "input":
                session.send(message.get("data") or "")
            elif kind == "resize":
                session.resize(message.get("cols") or 120, message.get("rows") or 32)
            elif kind == "confirm":
                session.confirm(bool(message.get("allow")))
            elif kind == "close":
                session.close("操作员主动断开")
                break
    except WebSocketDisconnect:
        session.close("浏览器断开")
    except Exception:                                       # noqa: BLE001
        session.close("通道异常")
    finally:
        session.close()
        try:
            await asyncio.wait_for(pump_task, timeout=6)
        except Exception:
            pump_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/stats")
def stats():
    """会话与命令的汇总（给页面顶部的 KPI 卡用）。"""
    data = remote.sessions(limit=200)
    store = get_store()
    with store.connect() as conn:
        commands = conn.execute("SELECT count(*) FROM remote_commands").fetchone()[0]
        blocked = conn.execute(
            "SELECT count(*) FROM remote_commands WHERE action IN ('block','cancel')"
        ).fetchone()[0]
        today = conn.execute(
            "SELECT count(*) FROM remote_sessions WHERE date(started_at)=date('now','localtime')"
        ).fetchone()[0]
    return {"sessions": data, "commands": commands, "blocked": blocked,
            "today": today, "credentials": len(remote.credentials_list())}

