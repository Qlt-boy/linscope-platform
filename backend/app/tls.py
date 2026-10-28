# -*- coding: utf-8 -*-
"""自签名 TLS 证书：首次启动生成，保存在持久化数据目录中。

迁移时只要完整迁移 backend/data（Docker 数据卷），证书和私钥会一起保留。
由于证书不受公共 CA 信任，浏览器会显示"不安全"，可点击"高级 -> 继续访问"。
"""
from __future__ import annotations

import ipaddress
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _split_hosts(value: str) -> list[str]:
    hosts = []
    for item in (value or "").split(","):
        host = item.strip()
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def ensure_self_signed(cert_path: str | os.PathLike, key_path: str | os.PathLike,
                       hosts: str = "localhost,127.0.0.1") -> dict:
    """确保证书和私钥存在；不存在时生成 10 年有效期的自签名证书。"""
    cert_file = Path(cert_path)
    key_file = Path(key_path)
    if cert_file.is_file() and cert_file.stat().st_size > 0 \
            and key_file.is_file() and key_file.stat().st_size > 0:
        return {"created": False, "cert": str(cert_file), "key": str(key_file)}

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    cert_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.parent.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LinScope Technology"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Network Operations Center"),
        x509.NameAttribute(NameOID.COMMON_NAME, "LinScopePlatform"),
    ])

    san = []
    for host in _split_hosts(hosts):
        try:
            san.append(x509.IPAddress(ipaddress.ip_address(host)))
        except ValueError:
            san.append(x509.DNSName(host))
    if not san:
        san = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=True,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False,
        ), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
                       critical=False)
        .sign(private_key, hashes.SHA256())
    )

    key_file.write_bytes(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    try:
        os.chmod(key_file, 0o600)
        os.chmod(cert_file, 0o644)
    except OSError:
        pass
    return {"created": True, "cert": str(cert_file), "key": str(key_file)}
