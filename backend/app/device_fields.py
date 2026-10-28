"""Validation shared by device creation and CSV import."""
from ipaddress import ip_address


def normalize_management_ip(value) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("IP 地址不能为空")
    try:
        return str(ip_address(text))
    except ValueError:
        raise ValueError("IP 地址格式无效，请填写 IPv4 或 IPv6 地址") from None
