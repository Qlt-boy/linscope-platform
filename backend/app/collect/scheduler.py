# -*- coding: utf-8 -*-
"""定时采集：一个后台守护线程，按「采集周期」跑一轮（可在系统设置里开关）。

刻意不用 APScheduler 之类的依赖：就一个 while + sleep 的线程，加一把锁防止上一轮没跑完
又开一轮。周期改了下一次循环立刻生效，不用重启。
"""
from __future__ import annotations

import threading
import time

from . import runner

_LOCK = threading.Lock()
_STATE = {"thread": None, "running": False, "last_started": "", "last_finished": "",
          "last_result": None}
_HEARTBEAT = 15          # 每 15 秒看一次设置，周期到了就采


def _loop() -> None:
    while True:
        try:
            conf = runner.settings()
            enabled = str(conf.get("enabled", "1")).lower() in ("1", "true", "on", "yes")
            interval = max(5, int(conf.get("interval_minutes") or 60)) * 60
            if enabled and _STATE["last_finished"]:
                if time.time() - _STATE["finished_ts"] >= interval:
                    run_once("schedule")
        except Exception:
            pass
        time.sleep(_HEARTBEAT)


def start() -> bool:
    """启动调度线程（幂等）。"""
    if _STATE["thread"] and _STATE["thread"].is_alive():
        return False
    thread = threading.Thread(target=_loop, daemon=True, name="collect-scheduler")
    _STATE["thread"] = thread
    _STATE["finished_ts"] = time.time()
    _STATE["last_finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    thread.start()
    return True


def run_once(trigger: str = "schedule") -> dict | None:
    """跑一轮（加锁，避免与手动采集撞车）。"""
    if not _LOCK.acquire(blocking=False):
        return None
    try:
        _STATE["running"] = True
        _STATE["last_started"] = time.strftime("%Y-%m-%d %H:%M:%S")
        result = runner.run(trigger=trigger,
                            operator="scheduler" if trigger == "schedule" else "system")
        _STATE["last_result"] = result
        return result
    finally:
        _STATE["finished_ts"] = time.time()
        _STATE["last_finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _STATE["running"] = False
        _LOCK.release()


def state() -> dict:
    return {"running": _STATE["running"], "last_started": _STATE["last_started"],
            "last_finished": _STATE["last_finished"],
            "last_result": _STATE["last_result"]}