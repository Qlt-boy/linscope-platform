# -*- coding: utf-8 -*-
"""本机实验用的「假华为交换机」（VRP），给自带采集模块做端到端自测。

它按 VRP 的真实回显格式返回几条常用命令的输出，让采集器能被真实验证：

    display version / display device manuinfo / display cpu-usage
    display memory-usage / display interface / display interface brief
    display stp brief / display current-configuration / display alarm

用法：
    python backend/tools/fake_huawei_switch.py --port 2223 --user netadmin \
        --password netadmin123 --log backend/data/fake_huawei.log
"""
from __future__ import annotations

import argparse
import datetime
import os
import socket
import threading
import time

import paramiko

HOST_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "fake_huawei_host_key")
HOSTNAME = "HW-S5720-01"          # 单台模式（--count 1）时使用

#: 多台档位：一次起 N 台不同状态的交换机（hostname / 型号 / CPU / 内存 / 端口 / STP / 告警）
PROFILES = [
    {"host": "HW-CORE-SW01", "model": "S6720-30C-EI-24S",
     "cpu": 12, "mem": 38, "down": [], "err": {}, "stp": "enabled",
     "alarms": [], "desc": "核心交换机 · 全部正常"},
    {"host": "HW-AGG-SW01", "model": "S5731-H48T4XC",
     "cpu": 23, "mem": 45, "down": [], "err": {"GigabitEthernet0/0/24": {"crc": 5, "errors": 2}},
     "stp": "enabled", "alarms": [], "desc": "汇聚交换机 · 少量错包"},
    {"host": "HW-ACC-SW01", "model": "S5720-28X-SI-AC",
     "cpu": 78, "mem": 86, "down": ["GigabitEthernet0/0/2"],
     "err": {"GigabitEthernet0/0/3": {"crc": 21, "errors": 7}}, "stp": "enabled",
     "alarms": [("Major", "The link of GigabitEthernet0/0/2 is down.")],
     "desc": "接入交换机 · 端口 down + 错包 + CPU/内存偏高"},
    {"host": "HW-ACC-SW02", "model": "S5735-L24T4S-A",
     "cpu": 9, "mem": 33, "down": [], "err": {}, "stp": "disabled",
     "alarms": [], "desc": "接入交换机 · STP 未启用（演示异常判定）"},
    {"host": "HW-EDGE-SW01", "model": "S5720-52X-SI-AC",
     "cpu": 15, "mem": 41, "down": [], "err": {}, "stp": "enabled",
     "alarms": [], "desc": "边缘交换机 · 全部正常"},
]

VERSION = """Huawei Versatile Routing Platform Software
VRP (R) software, Version 5.170 (S5720 V200R019C10SPC500)
Copyright (C) 2012-2020 Huawei Technologies Co., Ltd.
HUAWEI S5720-28X-SI-AC Routing Switch uptime is 123 days, 4 hours, 5 minutes
BKP  Version information:
1. PCB    Version  : CEM28XSI01 VER A
2. Board  Type     : S5720-28X-SI-AC
3. MPU    Type     : MainBoard
"""

MANUINFO = """Device Serial Number:210235448510E1000123
Manufactured board information:
  Board Name: S5720-28X-SI-AC
  Board Serial number:210235448510E1000123
"""

CPU = """CPU Usage Stat. Cycle: 60 (Second)
CPU Usage            : 11%  Max: 46%
CPU Usage Stat. Time : 2026-10-16  09:15:03
CPU utilization for five seconds: 11%: one minute: 9%: five minutes: 8%
"""

MEMORY = """Memory utilization statistics at 2026-10-16 09:15:03
System Total Memory: 1024 MB
Total Used Memory: 361 MB (35%)
"""

INTERFACE = """GigabitEthernet0/0/1 current state : UP
Line protocol current state : UP
Description:to-core-switch
Switch Port, PVID :    1, TPID : 8100(Hex), The Maximum Frame Length is 9216
IP Sending Frames' Format is PKTFMT_ETHNT_2, Hardware address is 00e0-fc12-3456
Input bandwidth utilization  :    1%
Output bandwidth utilization :    2%
Input: 1024 packets, 131072 bytes
  Unicast: 1000, Multicast: 24, Broadcast: 0
  Errors: 3, Runts: 0, Giants: 0, CRC: 2, OverRun: 0, Fragment: 1
Output: 2048 packets, 262144 bytes
  Unicast: 2000, Multicast: 48, Broadcast: 0
  Errors: 0, Collisions: 0
GigabitEthernet0/0/2 current state : DOWN
Line protocol current state : DOWN
Description:to-floor2
Input bandwidth utilization  :    0%
Output bandwidth utilization :    0%
Input: 0 packets, 0 bytes
  Errors: 0, CRC: 0
Output: 0 packets, 0 bytes
  Errors: 0, Collisions: 0
GigabitEthernet0/0/3 current state : UP
Line protocol current state : UP
Input bandwidth utilization  :   35%
Output bandwidth utilization :   42%
Input: 999 packets, 1 bytes
  Errors: 12, CRC: 9, OverRun: 3
Output: 999 packets, 1 bytes
  Errors: 0
"""

INTERFACE_BRIEF = """PHY: Physical
*down: administratively down
Interface                   PHY     Protocol InUti OutUti   inErrors  outErrors
GigabitEthernet0/0/1        up      up          1%     2%          3          0
GigabitEthernet0/0/2        down    down        0%     0%          0          0
GigabitEthernet0/0/3        up      up         35%    42%         12          0
"""

STP_BRIEF = """MSTID   Port                        Role  STP State       Protection
0       GigabitEthernet0/0/1        ROOT  FORWARDING      NONE
0       GigabitEthernet0/0/3        DESI  FORWARDING      NONE
0       GigabitEthernet0/0/2        ALTE  DISCARDING      NONE
"""

ALARM = """Alarm ID   Date                Time      Severity  Info
0x00010001 2026-10-15          03:41:22  Major     The link of GigabitEthernet0/0/2 is down.
"""

CONFIG = """#
sysname HW-S5720-01
#
vlan batch 10 20 100
#
interface Vlanif100
 ip address 10.10.9.1 255.255.255.0
#
interface GigabitEthernet0/0/1
 description to-core-switch
 port link-type trunk
 port trunk allow-pass vlan 10 20 100
#
return
"""


#: --jitter 打开时，每次连接给这台的 CPU/内存/错包加一点波动（模拟真实设备）
JITTER = {"on": False, "tick": {}}


def refresh_jitter(profile: dict) -> None:
    if not JITTER["on"]:
        return
    import random
    host = profile["host"]
    JITTER["tick"][host] = {
        "cpu": random.randint(-8, 35),
        "mem": random.randint(-5, 20),
        "err": random.randint(0, 60),
    }


def jitter_of(profile: dict) -> dict:
    return JITTER["tick"].get(profile["host"], {"cpu": 0, "mem": 0, "err": 0})


#: --flap 打开时，每次连接切换指定端口 up/down（演示"端口新变 down / 已恢复"）
FLAP = {"port": "", "state": {}}


def refresh_flap(profile: dict) -> None:
    port = FLAP.get("port") or ""
    if not port:
        return
    host = profile["host"]
    down = not FLAP["state"].get(host, True)     # 第一次连接先让端口是 up
    FLAP["state"][host] = down
    downs = list(profile.get("down") or [])
    if down and port not in downs:
        downs.append(port)
    elif not down and port in downs:
        downs.remove(port)
    profile["down"] = downs


def host_seed(host: str) -> int:
    """稳定的每台种子：用 crc32 而不是内置 hash()（hash() 每个进程都不一样，
    重启假设备会让 uptime 变小，变化检测会误报"设备重启"）。"""
    import zlib
    return zlib.crc32(host.encode("utf-8"))


def profile_version(profile: dict) -> str:
    host, model = profile["host"], profile["model"]
    seed = host_seed(host)
    return VERSION.replace("HUAWEI S5720-28X-SI-AC Routing Switch uptime is 123 days, 4 hours, 5 minutes",
                           "HUAWEI %s Routing Switch uptime is %d days, %d hours, %d minutes"
                           % (model, 123 + seed % 90, seed % 23, seed % 59)) \
                  .replace("Board  Type     : S5720-28X-SI-AC", "Board  Type     : %s" % model) \
                  .replace("S5720 V200R019C10SPC500",
                           "%s V200R0%d9C10SPC500" % (model.split("-")[0], 1 + seed % 2))


def profile_manuinfo(profile: dict) -> str:
    serial = "210235448510E1%05d" % (host_seed(profile["host"]) % 100000)
    return MANUINFO.replace("210235448510E1000123", serial)


def profile_cpu(profile: dict) -> str:
    cpu = max(1, min(99, profile["cpu"] + jitter_of(profile)["cpu"]))
    return CPU.replace("11%", "%d%%" % cpu).replace("Max: 46%", "Max: %d%%" % min(99, cpu + 25)) \
              .replace("five seconds: 11%", "five seconds: %d%%" % cpu)


def profile_memory(profile: dict) -> str:
    mem = max(1, min(99, profile["mem"] + jitter_of(profile)["mem"]))
    return MEMORY.replace("(35%)", "(%d%%)" % mem)


def _ports(profile: dict) -> list:
    base = ["GigabitEthernet0/0/1", "GigabitEthernet0/0/2", "GigabitEthernet0/0/3",
            "GigabitEthernet0/0/24"]
    return base


def profile_interface(profile: dict) -> str:
    blocks = []
    for name in _ports(profile):
        down = name in profile.get("down", [])
        err = dict(profile.get("err", {}).get(name, {}))
        if err:                      # 只有本来就有错包的端口才跟着波动，干净口保持 0
            err["errors"] = err.get("errors", 0) + jitter_of(profile)["err"]
        blocks.append(
            "%s current state : %s\n"
            "Line protocol current state : %s\n"
            "Description:%s\n"
            "Input bandwidth utilization  :    %d%%\n"
            "Output bandwidth utilization :    %d%%\n"
            "Input: 1024 packets, 131072 bytes\n"
            "  Errors: %d, Runts: 0, Giants: 0, CRC: %d, OverRun: 0\n"
            "Output: 2048 packets, 262144 bytes\n"
            "  Errors: 0, Collisions: 0\n"
            % (name, "DOWN" if down else "UP", "DOWN" if down else "UP",
               ("to-" + profile["host"].lower()) if name.endswith("/1") else "",
               1 if not down else 0, 2 if not down else 0,
               err.get("errors", 0), err.get("crc", 0)))
    return "\n".join(blocks)


def profile_interface_brief(profile: dict) -> str:
    lines = ["PHY: Physical", "Interface                   PHY     Protocol "
             "InUti OutUti   inErrors  outErrors"]
    for name in _ports(profile):
        down = name in profile.get("down", [])
        err = dict(profile.get("err", {}).get(name, {}))
        if err:                      # 同上：只让有错包的口波动
            err["errors"] = err.get("errors", 0) + jitter_of(profile)["err"]
        lines.append("%-27s %-7s %-9s %4d%% %5d%% %10d %10d"
                     % (name, "down" if down else "up", "down" if down else "up",
                        0 if down else 1, 0 if down else 2,
                        err.get("errors", 0), err.get("crc", 0)))
    return "\n".join(lines) + "\n"


def profile_lldp(profile: dict) -> str:
    """display lldp neighbor 的样例回显（四列：本端口 / 邻居设备 / 邻居口 / 存活秒数）。"""
    return ("Local Intf          Neighbor Dev             Neighbor Intf       Exptime(s)\n"
            "GE0/0/1             LAB-CORE-01              GE0/0/2             121\n"
            "GE0/0/2             LAB-ACC-02               GE0/0/24            118\n")


def profile_stp(profile: dict) -> str:
    if profile.get("stp") == "disabled":
        return "\n  (STP 未启用)\n"
    return STP_BRIEF


def profile_alarm(profile: dict) -> str:
    if not profile.get("alarms"):
        return "Alarm ID   Date                Time      Severity  Info\n"
    head = "Alarm ID   Date                Time      Severity  Info\n"
    body = "".join("0x%08x 2026-10-15          03:%02d:22  %-9s %s\n"
                   % (abs(hash(profile["host"] + info)) % 0xffffffff, idx + 10, sev, info)
                   for idx, (sev, info) in enumerate(profile["alarms"]))
    return head + body


def profile_config(profile: dict) -> str:
    return ("#\nsysname %s\n#\nvlan batch 10 20 100\n#\n"
            "interface Vlanif100\n ip address 10.10.9.1 255.255.255.0\n#\n"
            "interface GigabitEthernet0/0/1\n description uplink-%s\n"
            " port link-type trunk\n port trunk allow-pass vlan 10 20 100\n#\nreturn\n"
            % (profile["host"], profile["host"]))


class HuaweiServer(paramiko.ServerInterface):
    def __init__(self, user: str, password: str, log_path: str):
        self.user = user
        self.password = password
        self.log_path = log_path
        self.shell = threading.Event()

    def check_auth_password(self, username, password):
        return (paramiko.AUTH_SUCCESSFUL
                if username == self.user and password == self.password
                else paramiko.AUTH_FAILED)

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_request(self, kind, chanid):
        return (paramiko.OPEN_SUCCEEDED if kind == "session"
                else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED)

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth,
                                  pixelheight, modes):
        return True

    def check_channel_shell_request(self, channel):
        self.shell.set()
        return True


def log_command(log_path: str, command: str) -> None:
    if not log_path:
        return
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write("%s\t%s\n" % (
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), command))


def respond(server: "HuaweiServer", channel, command: str, profile: dict) -> None:
    log_command(server.log_path, command)
    low = command.lower().strip()
    if not low:
        return
    if low.startswith("screen-length"):
        return
    if low.startswith("display version"):
        channel.send(profile_version(profile))
        return
    if low.startswith("display device manuinfo") or low.startswith("display esn"):
        channel.send(profile_manuinfo(profile))
        return
    if low.startswith("display cpu-usage"):
        channel.send(profile_cpu(profile))
        return
    if low.startswith("display memory-usage") or low.startswith("display memory"):
        channel.send(profile_memory(profile))
        return
    if low.startswith("display interface brief"):
        channel.send(profile_interface_brief(profile))
        return
    if low.startswith("display interface"):
        channel.send(profile_interface(profile))
        return
    if low.startswith("display stp brief") or low.startswith("display stp"):
        channel.send(profile_stp(profile))
        return
    if low.startswith("display lldp neighbor"):
        channel.send(profile_lldp(profile))
        return
    if low.startswith("display alarm"):
        channel.send(profile_alarm(profile))
        return
    if low.startswith("display current-configuration") or low.startswith("display cu"):
        channel.send(profile_config(profile))
        return
    if low.startswith("display"):
        channel.send("\n  (fake huawei) 未实现该命令\n")
        return
    channel.send("\nError: Unrecognized command found at '^' position.\n")


def serve_client(client: socket.socket, address, args, profile: dict) -> None:
    transport = paramiko.Transport(client)
    transport.add_server_key(paramiko.RSAKey(filename=host_key_path()) if
                             os.path.exists(host_key_path()) else _gen_key())
    server = HuaweiServer(args.user, args.password, args.log)
    try:
        transport.start_server(server=server)
    except Exception:
        return
    channel = transport.accept(20)
    if channel is None:
        transport.close()
        return
    server.shell.wait(20)
    refresh_jitter(profile)
    refresh_flap(profile)
    channel.send("\r\n")
    channel.send("<%s> " % profile["host"])
    buffer = ""
    try:
        while True:
            data = channel.recv(4096)
            if not data:
                break
            for ch in data.decode("utf-8", "replace"):
                if ch in ("\r", "\n"):
                    channel.send("\r\n")
                    respond(server, channel, buffer.strip(), profile)
                    buffer = ""
                    channel.send("<%s> " % profile["host"])
                elif ch == "\x7f":
                    if buffer:
                        buffer = buffer[:-1]
                        channel.send("\b \b")
                elif ch == "\x03":
                    buffer = ""
                    channel.send("^C\r\n<%s> " % profile["host"])
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


def host_key_path() -> str:
    return HOST_KEY_FILE


def _gen_key():
    if not os.path.exists(HOST_KEY_FILE):
        paramiko.RSAKey.generate(2048).write_private_key_file(HOST_KEY_FILE)
    return paramiko.RSAKey(filename=HOST_KEY_FILE)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2223)
    parser.add_argument("--user", default="netadmin")
    parser.add_argument("--password", default="netadmin123")
    parser.add_argument("--log", default=os.path.join("data", "fake_huawei.log"))
    parser.add_argument("--count", type=int, default=1, help="一次起几台（按内置档位）")
    parser.add_argument("--jitter", action="store_true", help="每次连接给 CPU/内存/错包加波动（演示变化告警）")
    parser.add_argument("--flap", default="", metavar="PORT",
                        help="每次连接切换该端口 up/down，如 GigabitEthernet0/0/2（演示端口变化告警）")
    args = parser.parse_args()

    _gen_key()
    JITTER["on"] = bool(args.jitter)
    FLAP["port"] = (args.flap or "").strip()
    count = max(1, min(len(PROFILES), args.count))
    for index in range(count):
        profile = PROFILES[index % len(PROFILES)]
        if count > 1:
            # 多台模式：每台一个回环地址（127.0.0.2 / .3 / …），端口保持一致；
            # 平台的设备台账按 IP 建索引，用同一 IP 多端口会被合并成一台。
            host = "127.0.0.%d" % (2 + index)
            port = args.port
        else:
            host, port = args.host, args.port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(20)
        threading.Thread(
            target=lambda s=sock, p=profile: _accept_loop(s, args, p),
            daemon=True).start()
        print("假华为交换机 #%d：%s（%s）→ ssh %s@%s -p %d"
              % (index + 1, profile["host"], profile["desc"], args.user, host, port),
              flush=True)
    print("（波动：%s；端口翻转：%s；命令回显日志：%s；Ctrl+C 退出）"
          % ("开" if args.jitter else "关", args.flap or "关", args.log), flush=True)
    while True:
        time.sleep(3600)


def _accept_loop(sock: socket.socket, args, profile: dict) -> None:
    while True:
        try:
            client, address = sock.accept()
        except OSError:
            return
        threading.Thread(target=serve_client, args=(client, address, args, profile),
                         daemon=True).start()


if __name__ == "__main__":
    main()