# -*- coding: utf-8 -*-
"""远程登录控制台的端到端自测：WebSocket → 后端 → SSH → 假交换机。

覆盖：会话建立、正常命令回显、硬拦截（破坏性命令连回车都不发）、
变更类命令人工确认（放行 / 拒绝）、确认期间输入冻结、会话与命令留痕。
"""
import asyncio, json, os, pathlib

import ssl

import websockets

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

API = "https://127.0.0.1:1314/api"
TARGET_IP = "127.0.0.1"
WS_TMPL = ("wss://127.0.0.1:1314/api/remote/session/%s?operator=selftest&token=%%s"
           % TARGET_IP)


def login():
    """全站已鉴权：先登录拿令牌，WS 用 ?token= 带过去。"""
    import urllib.request
    password = os.environ.get("NIP_ADMIN_PASSWORD") or "LinScope@2026"
    body = json.dumps({"username": "admin", "password": password}).encode()
    req = urllib.request.Request(API + "/auth/login", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp:
        return json.loads(resp.read().decode())["token"]
# 假设备把命令日志写在 backend/data/fake_ssh.log（按脚本位置解析，换工作目录也不会读错）
LOG = pathlib.Path(__file__).resolve().parents[1] / "data" / "fake_ssh.log"
events = []
FAILS = []


async def collect(ws, seconds, stop_on=()):
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=seconds)
            event = json.loads(raw)
            events.append(event)
            if event.get("type") in stop_on:
                break
    except asyncio.TimeoutError:
        pass


def out_text():
    return "".join(e.get("data", "") for e in events if e.get("type") == "output")


def log_text():
    return LOG.read_text(encoding="utf-8") if LOG.exists() else ""


def check(name, cond, detail=""):
    print(("OK   " if cond else "FAIL ") + name + ("" if cond else "  ← " + str(detail)))
    if not cond:
        FAILS.append(name)


async def pending_confirm(): 
    return [e for e in events if e.get("type") == "confirm"]


def api(path, method="GET", body=None, token=""):
    import urllib.error
    import urllib.request
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:200]


def ensure_target(token):
    """远程登录只允许连**设备台账里**的设备：自测目标缺了就补一条（仅台账，不碰真实设备）。"""
    status, _ = api("/devices/" + TARGET_IP, token=token)
    if status == 200:
        print("OK   自测目标已在台账里：%s" % TARGET_IP)
        return True
    status, payload = api("/devices", "POST", {
        "ip": TARGET_IP, "name": "LAB-SSH-01", "vendor": "h3c",
        "vendor_display": "华三", "kind": "switch", "group": "实验室",
        "role": "远程登录自测靶机", "port": 2223,
    }, token)
    print(("OK   " if status == 200 else "FAIL ") + "补一条自测设备到台账：%s %s"
          % (TARGET_IP, "" if status == 200 else payload))
    return status == 200


async def main():
    if LOG.exists():
        LOG.unlink()
    token = login()
    if not ensure_target(token):
        FAILS.append("自测设备缺失")
    async with websockets.connect(WS_TMPL % token, max_size=None, ssl=SSL_CONTEXT) as ws:
        await collect(ws, 3, stop_on=("ready",))
        await collect(ws, 1.2)
        ready = [e for e in events if e.get("type") == "ready"]
        check("会话建立并回报会话信息", bool(ready) and ready[0]["session"]["device_ip"] == "127.0.0.1")

        await ws.send(json.dumps({"type": "input", "data": "display version\r"}))
        await collect(ws, 2)
        check("正常命令有回显（display version）", "LAB-FAKE" in out_text())

        # 硬拦截：format flash: —— 破坏性命令，回车不下发
        before = len(events)
        await ws.send(json.dumps({"type": "input", "data": "format flash:\r"}))
        await collect(ws, 2)
        blocks = [e for e in events[before:] if e.get("type") == "notice" and "已拦截" in e.get("text", "")]
        check("破坏性命令被硬拦截并提示", bool(blocks), blocks)
        check("被拦截的命令没有在设备上执行", "format" not in log_text())

        # 变更类：reboot → 需确认 → 人工拒绝
        before = len(events)
        await ws.send(json.dumps({"type": "input", "data": "reboot\r"}))
        await collect(ws, 3, stop_on=("confirm",))
        confirms = [e for e in events[before:] if e.get("type") == "confirm"]
        check("reboot 触发人工确认", bool(confirms), confirms)
        # 确认未决期间键入的内容应被冻结（不应直接到设备）
        await ws.send(json.dumps({"type": "input", "data": "display memory"}))
        await collect(ws, 1)
        await ws.send(json.dumps({"type": "confirm", "id": confirms[0]["id"] if confirms else 0, "allow": False}))
        await collect(ws, 2)
        check("拒绝后 reboot 未执行", "reboot" not in log_text(), log_text().replace("\n", " | "))

        # 变更类：undo ... → 确认 → 放行
        before = len(events)
        await ws.send(json.dumps({"type": "input", "data": "undo ip route-static 0.0.0.0 0 1.1.1.1\r"}))
        await collect(ws, 3, stop_on=("confirm",))
        confirms2 = [e for e in events[before:] if e.get("type") == "confirm"]
        await ws.send(json.dumps({"type": "confirm", "id": confirms2[0]["id"] if confirms2 else 0, "allow": True}))
        await collect(ws, 2)
        check("放行后命令在设备上执行", "undo ip route-static 0.0.0.0 0 1.1.1.1" in log_text())

        # 确认未决期间键入的内容按设计**丢弃**（补发会拼进下一行，容易出事故）
        await collect(ws, 2)
        drop = [e for e in events if e.get("type") == "notice" and "已丢弃" in e.get("text", "")]
        check("确认期间键入的内容被丢弃并提示", bool(drop) and "display memory" not in log_text(),
              log_text().replace("\n", " | "))

        # save force → 拒绝
        before = len(events)
        await ws.send(json.dumps({"type": "input", "data": "save force\r"}))
        await collect(ws, 3, stop_on=("confirm",))
        c3 = [e for e in events[before:] if e.get("type") == "confirm"]
        await ws.send(json.dumps({"type": "confirm", "id": c3[0]["id"] if c3 else 0, "allow": False}))
        await collect(ws, 2)
        check("拒绝后 save force 未执行", "save force" not in log_text())

        await ws.send(json.dumps({"type": "close"}))
        await collect(ws, 2, stop_on=("closed",))

    print("\n设备实际执行过的命令：")
    for line in log_text().strip().splitlines():
        print("   ", line)
    print("\n结果：" + ("全部通过" if not FAILS else "失败 " + str(len(FAILS)) + " 项：" + "、".join(FAILS)))


asyncio.run(main())
