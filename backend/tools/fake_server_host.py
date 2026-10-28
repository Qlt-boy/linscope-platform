# -*- coding: utf-8 -*-
"""本机实验用的「假 Linux 服务器」：最小 SSH 服务端，只实现 exec 通道。

服务器采集走的是 paramiko 的 exec_command（非交互 shell），所以这里对每条命令
返回固定回显，用来端到端验证「采集 → 回显留档 → 报告截图」整条链路。

用法（一般由 server_collect_selftest.py 在进程内起）：
    python backend/tools/fake_server_host.py --port 2223 --user root --password root123
"""
from __future__ import annotations

import argparse
import os
import queue
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


LINUX_OUTPUTS = [
    ("uname -s", "Linux"),
    ("uname -srm", "Linux 5.15.0-91-generic x86_64"),
    ("os-release", 'NAME="Ubuntu"\nVERSION="22.04.3 LTS (Jammy Jellyfish)"\n'
                   'PRETTY_NAME="Ubuntu 22.04.3 LTS"\nID=ubuntu\nVERSION_ID="22.04"'),
    ("dmi", "Dell Inc.\nPowerEdge R750\nABC1234"),
    ("hostname", "srv-app-01"),
    ("uptime", " 09:15:03 up 12 days,  3:21,  1 user,  load average: 0.52, 0.61, 0.58"),
    ("top -bn1", "top - 09:15:03 up 12 days,  3:21,  1 user,  load average: 0.52\n"
                 "Tasks: 231 total,   1 running, 230 sleeping\n"
                 "%Cpu(s):  3.2 us,  1.0 sy,  0.0 ni, 95.4 id,  0.4 wa,  0.0 hi,  0.0 si"),
    ("free -m", "               total        used        free      shared  buff/cache   available\n"
                "Mem:           64257       12345       10000         123       41912       51234\n"
                "Swap:           8191           0        8191"),
    ("df -hT", "Filesystem     Type  Size  Used Avail Use% Mounted on\n"
               "/dev/sda2      ext4  200G  120G   70G  63% /\n"
               "/dev/sdb1      xfs   2.0T  1.2T  700G  63% /data"),
    ("ip -br", "lo               UNKNOWN        127.0.0.1/8\n"
               "ens192           UP             10.20.30.11/24"),
    ("systemctl --failed", "  UNIT  LOAD  ACTIVE SUB  DESCRIPTION\n0 loaded units listed."),
    ("journalctl", "-- Logs begin at Mon 2026-09-01 00:00:00 CST, end at Fri 2026-10-16 --\n"
                   "Oct 16 09:15:03 srv-app-01 systemd[1]: Failed to start nginx.service.\n"
                   "Oct 16 09:16:11 srv-app-01 kernel: EXT4-fs error on sda2"),
    ("thermal_zone", "/sys/class/thermal/thermal_zone0/temp 38500"),
    ("ls -lt", "-rw-r--r-- 1 root root 1288490188 Oct 16 02:00 backup_20261016.tar.gz\n"
               "-rw-r--r-- 1 root root  644245094 Oct 15 02:00 backup_20261015.tar.gz"),
]


def respond(command: str) -> str:
    for keyword, output in LINUX_OUTPUTS:
        if keyword in command:
            return output
    return ""


class FakeHost(paramiko.ServerInterface):
    def __init__(self, user: str, password: str):
        self.user = user
        self.password = password
        # 一条 SSH 连接上会连续开多个 exec 通道（每条采集命令一个），用队列接住
        self.commands: "queue.Queue[str]" = queue.Queue()

    def check_auth_password(self, username, password):
        return (paramiko.AUTH_SUCCESSFUL if username == self.user and password == self.password
                else paramiko.AUTH_FAILED)

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_request(self, kind, chanid):
        return (paramiko.OPEN_SUCCEEDED if kind == "session"
                else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED)

    def check_channel_exec_request(self, channel, command):
        text = command.decode("utf-8", "replace") if isinstance(command, bytes) else command
        self.commands.put(text)
        return True


def serve_client(client_socket, args):
    transport = paramiko.Transport(client_socket)
    transport.add_server_key(host_key())
    server = FakeHost(args.user, args.password)
    try:
        transport.start_server(server=server)
    except Exception:                                   # noqa: BLE001
        return
    try:
        while transport.is_active():
            channel = transport.accept(20)
            if channel is None:
                break
            try:
                command = server.commands.get(timeout=15)
            except queue.Empty:
                channel.close()
                continue
            output = respond(command)
            try:
                if output:
                    channel.send(output.encode("utf-8")
                                 + (b"" if output.endswith("\n") else b"\n"))
                channel.send_exit_status(0)
            except Exception:                           # noqa: BLE001
                pass
            finally:
                try:
                    channel.close()
                except Exception:                       # noqa: BLE001
                    pass
    finally:
        transport.close()


def serve(host: str = "127.0.0.1", port: int = 2223, user: str = "root", password: str = "root123"):
    """在当前进程里起一个监听（后台线程），返回 (thread, port)。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(20)
    actual = sock.getsockname()[1]
    args = argparse.Namespace(user=user, password=password)

    def loop():
        while True:
            try:
                client, _address = sock.accept()
            except OSError:
                return
            threading.Thread(target=serve_client, args=(client, args), daemon=True).start()

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread, sock, actual


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2223)
    parser.add_argument("--base", type=int, default=12)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="root123")
    args = parser.parse_args()
    socks = []
    count = max(1, args.count)
    for index in range(count):
        host = "127.0.0.%d" % (args.base + index) if count > 1 else args.host
        _, sock, actual = serve(host, args.port, args.user, args.password)
        socks.append(sock)
        print("假服务器 #%d 已启动：ssh %s@%s -p %d" % (index + 1, args.user, host, actual), flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        for sock in socks:
            sock.close()


if __name__ == "__main__":
    main()
