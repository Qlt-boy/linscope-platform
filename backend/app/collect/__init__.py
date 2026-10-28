# -*- coding: utf-8 -*-
"""自带采集：华为 VRP 交换机 + Linux / Windows(OpenSSH) 服务器。

模块划分：
* `huawei.py`  —— 交换机命令清单 + 回显解析（纯函数，可单测）
* `server.py`  —— 服务器命令清单 + 回显解析（Linux / Windows，纯函数，可单测）
* `runner.py`  —— SSH 执行、并发、写库、采集日志
* `importer.py`—— 设备台账 CSV 批量导入
"""
from __future__ import annotations

from .importer import import_devices_csv, device_import_template_csv  # noqa: F401

__all__ = ["import_devices_csv", "device_import_template_csv"]
