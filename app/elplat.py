"""Клиент API СБП НКО ЭЛПЛАТ (createQr, getPay)."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import re
from decimal import Decimal
from typing import Any

import httpx

FORBIDDEN_PURPOSE_CHARS = re.compile(r"[\\'\"]")
ELPLAT_CALLBACK_NET = ipaddress.ip_network("91.223.44.0/24")


def elplat_enabled() -> bool:
    return os.getenv("ELPLAT_ENABLED", "").lower() in ("1", "true", "yes")


def elplat_config() -> dict[str, str]:
    return {
        "api_url": (os.getenv("ELPLAT_API_URL") or "http://sbpekvtest.el-plat.ru").rstrip("/"),
        "login": os.getenv("ELPLAT_LOGIN", "").strip(),
        "password": os.getenv("ELPLAT_PASSWORD", "").strip(),
        "org_id": os.getenv("ELPLAT_ORG_ID", "").strip(),
    }


def elplat_ready() -> bool:
    if not elplat_enabled():
        return False
    cfg = elplat_config()
    return bool(cfg["login"] and cfg["password"] and cfg["org_id"])


def public_base_url() -> str:
    return (os.getenv("PUBLIC_BASE_URL") or "http://localhost:8010").rstrip("/")


def callback_ip_allowed(client_host: str | None) -> bool:
    if os.getenv("ELPLAT_VERIFY_CALLBACK_IP", "").lower() in ("1", "true", "yes"):
        if not client_host:
            return False
        try:
            return ipaddress.ip_address(client_host) in ELPLAT_CALLBACK_NET
        except ValueError:
            return False
    return True


def md5_hex(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def sanitize_payment_purpose(text: str) -> str:
    cleaned = FORBIDDEN_PURPOSE_CHARS.sub(" ", text)
    return cleaned.strip()[:140] or "Оплата заказа"


def create_qr_hash_id(
    login: str,
    passwd: str,
    callback: str,
    qrc_type: str,
    currency: str,
    org_id: str,
    amount: str = "",
    payment_purpose: str = "",
    email: str = "",
    redirect_url: str = "",
    subscription_purpose: str = "",
) -> str:
    payload = (
        login
        + passwd
        + callback
        + qrc_type
        + currency
        + org_id
        + amount
        + payment_purpose
        + email
        + redirect_url
        + subscription_purpose
    )
    return md5_hex(payload)


def get_pay_hash_id(login: str, passwd: str, qrc_id: str) -> str:
    return md5_hex(login + passwd + qrc_id)


def amount_kopecks(total: Decimal) -> str:
    return str(int((total * 100).quantize(Decimal("1"))))


async def api_request(body: dict[str, Any]) -> dict[str, Any]:
    cfg = elplat_config()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            cfg["api_url"],
            json=body,
            headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
        )
        response.raise_for_status()
        return response.json()


async def create_dynamic_qr(
    *,
    amount_rub: Decimal,
    payment_purpose: str,
    callback_url: str,
    redirect_url: str = "",
    email: str = "",
    qr_ttl_minutes: int = 60,
) -> dict[str, Any]:
    cfg = elplat_config()
    purpose = sanitize_payment_purpose(payment_purpose)
    amount = amount_kopecks(amount_rub)
    hash_id = create_qr_hash_id(
        cfg["login"],
        cfg["password"],
        callback_url,
        "02",
        "RUB",
        cfg["org_id"],
        amount,
        purpose,
        email,
        redirect_url,
        "",
    )
    body: dict[str, Any] = {
        "type": "createQr",
        "login": cfg["login"],
        "callback": callback_url,
        "qrcType": "02",
        "hashId": hash_id,
        "currency": "RUB",
        "orgId": cfg["org_id"],
        "amount": amount,
        "paymentPurpose": purpose,
        "qrTtl": str(max(5, min(qr_ttl_minutes, 129600))),
    }
    if email:
        body["email"] = email
    if redirect_url:
        body["redirectUrl"] = redirect_url

    data = await api_request(body)
    info = (data.get("info") or {}) if isinstance(data, dict) else {}
    if not info.get("status"):
        raise RuntimeError(info.get("descr") or "ЭЛПЛАТ: не удалось создать QR")
    return info


async def get_payment_status(qrc_id: str) -> dict[str, Any]:
    cfg = elplat_config()
    hash_id = get_pay_hash_id(cfg["login"], cfg["password"], qrc_id)
    body = {
        "type": "getPay",
        "login": cfg["login"],
        "qrcId": qrc_id,
        "hashId": hash_id,
    }
    data = await api_request(body)
    info = (data.get("info") or {}) if isinstance(data, dict) else {}
    if not info.get("status"):
        raise RuntimeError(info.get("descr") or "ЭЛПЛАТ: ошибка запроса статуса")
    return info
