# -*- coding: utf-8 -*-
"""本机实验用的「假交换机」：一个最小 SSH 服务端，给远程登录模块做端到端自测。

它不属于平台代码，也不模拟任何厂商设备，只做三件事：
 1. 用一个口令账号接受 SSH 登录并开一个交互式 shell（回显 + 提示符）；
 2. 认几条像交换机一样命令，**把真正执行过的命令写进日志文件**（便于断言「拦截生效」）；
 3. 其中 `reboot` / `save force` 这类危险命令会「真的执行」（写日志 + 打印回显），
    所以只要日志里没有它，就能证明平台的命令拦截确实把回车拦住了。

用法：
    python backend/tools/fake_ssh_device.py --port 2222 --user netadmin --password netadmin123 \
        --log backend/data/fake_ssh.log
"""
from __future__ import annotations

import argparse
import datetime
import os
import socket
import threading

import paramiko

HOST_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_ssh_host_key")


def host_key() -> "paramiko.RSAKey":
    if os.path.exists(HOST_KEY_FILE):
        return paramiko.RSAKey(filename=HOST_KEY_FILE)
    key = paramiko.RSAKey.generate(2048)
    key.write_private_key_file(HOST_KEY_FILE)
    return key


class SwitchServer(paramiko.ServerInterface):
    def __init__(self, user: str, password: str, log_path: str):
        self.user = user
        self.password = password
        self.log_path = log_path
        self.shell = threading.Event()

    def check_auth_password(self, username, password):
        if username == self.user and password == self.password:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED if kind == "session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth,
                                  pixelheight, modes):
        return True

    def check_channel_shell_request(self, channel):
        self.shell.set()
        return True


def log_command(log_path: str, command: str) -> None:
    if not log_path:
        return
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write("%s\t%s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                   command))


def respond(server: SwitchServer, channel, command: str) -> None:
    log_command(server.log_path, command)
    low = command.lower()
    if not command:
        return
    if low.startswith("screen-length") or low.startswith("terminal length"):
        return                                     # 关分屏：静默
    if low == "reboot":
        channel.send("\r\nSystem is rebooting... (fake device: 说明拦截没生效)\r\n")
        return
    if low.startswith("save force"):
        channel.send("\r\nNow saving the current configuration to the slot 1.\r\nSave the configuration successfully.\r\n")
        return
    if low.startswith("undo "):
        channel.send("\r\n%s done.\r\n" % command)
        return
    if low.startswith("display version"):
        channel.send("\r\nH3C Comware Software, Version 7.1.070, LAB-FAKE\r\n"
                     "LAB-SW01 uptime is 0 weeks, 3 days\r\n")
        return
    if low.startswith("display cpu-usage"):
        channel.send("\r\nSlot 1 CPU usage:\r\n   5% in last 5 seconds\r\n"
                     "   6% in last 1 minute\r\n")
        return
    if low.startswith("display memory"):
        channel.send("\r\nSystem Total Memory: 1024 MB\r\nTotal Used Memory: 322 MB (31%)\r\n")
        return
    if low.startswith("display"):
        channel.send("\r\n  (fake device) 仅演示用，未实现该 display 命令\r\n")
        return
    if low in ("system-view", "sys"):
        channel.send("\r\n[LAB-SW01]\r\n")
        return
    channel.send("\r\n  ^\n%% Unrecognized command found at '^' position.\r\n")


def serve_client(client: socket.socket, address, args) -> None:
    transport = paramiko.Transport(client)
    transport.add_server_key(host_key())
    server = SwitchServer(args.user, args.password, args.log)
    try:
        transport.start_server(server=server)
    except Exception:
        return
    channel = transport.accept(20)
    if channel is None:
        transport.close()
        return
    server.shell.wait(20)
    channel.send("\r\n* LAB-FAKE-SW01 (本机实验假交换机) *\r\n")
    channel.send("<LAB-SW01> ")
    buffer = ""
    try:
        while True:
            data = channel.recv(4096)
            if not data:
                break
            for ch in data.decode("utf-8", "replace"):
                if ch in ("\r", "\n"):
                    channel.send("\r\n")
                    respond(server, channel, buffer.strip())
                    buffer = ""
                    channel.send("<LAB-SW01> ")
                elif ch == "\x7f":
                    if buffer:
                        buffer = buffer[:-1]
                        channel.send("\b \b")
                elif ch == "\x03":
                    buffer = ""
                    channel.send("^C\r\n<LAB-SW01> ")
                elif ch == "\x1b":
                    continue
                elif ord(ch) < 32:
                    continue
                else:
                    buffer += ch
                    channel.send(ch)
    except Exception:
        pass
    finally:
        try:
            channel.close()
        except Exception:
            pass
        transport.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2222)
    parser.add_argument("--user", default="netadmin")
    parser.add_argument("--password", default="netadmin123")
    parser.add_argument("--log", default=os.path.join("data", "fake_ssh.log"))
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.listen(20)
    print("假交换机已启动：ssh %s@%s -p %d（命令日志：%s）"
          % (args.user, args.host, args.port, args.log), flush=True)
    while True:
        client, address = sock.accept()
        threading.Thread(target=serve_client, args=(client, address, args),
                         daemon=True).start()


if __name__ == "__main__":
    main()