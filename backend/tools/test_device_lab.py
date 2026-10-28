"""Opt-in loopback SSH lab. Never creates or collects business devices."""
from __future__ import annotations

import argparse
import os
import socket
import threading

from tools import fake_huawei_switch as switch
from tools import fake_server_host as server

_sockets = []


def endpoints():
    return ([(f"127.0.0.{i}", 2222, "switch", i - 2) for i in range(2, 7)]
            + [(f"127.0.0.{i}", 2223, "server", i - 12) for i in range(12, 17)]
            + [(f"127.0.0.{i}", 2224, "security", i - 7) for i in range(7, 12)]
            + [("127.0.1.21", 2222, "switch", 0),
               ("127.0.1.22", 2223, "server", 0),
               ("127.0.1.23", 2222, "switch", 2)])


def start():
    if _sockets or os.environ.get("NIP_TEST_LAB_ENABLED") != "1":
        return
    # Explicit lab only. No password is logged or returned by platform APIs.
    args = argparse.Namespace(user="netadmin", password="netadmin123", log="")
    from app.store import get_store
    devices = {d["ip"]: d for d in get_store().devices()}
    try:
        for ip, port, kind, index in endpoints():
            device = devices.get(ip, {})
            name = device.get("name", "")
            if not (name.startswith("TEST-") or name.startswith("FIELDS-TEST-")):
                continue
            if kind == "server":
                _, sock, _ = server.serve(ip, port, args.user, args.password)
            else:
                profile = dict(switch.PROFILES[index])
                profile["host"] = name
                if kind == "security":
                    profile["model"] = "USG6650E"
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind((ip, port))
                    sock.listen(20)
                except Exception:
                    sock.close()
                    raise
                threading.Thread(target=switch._accept_loop,
                                 args=(sock, args, profile), daemon=True).start()
            _sockets.append(sock)
    except Exception:
        stop()
        raise
    print(f"[test-lab] {len(_sockets)} loopback SSH endpoints ready", flush=True)


def stop():
    while _sockets:
        _sockets.pop().close()
