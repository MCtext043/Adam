"""Расчёт доставки: расстояние от кафе до адреса клиента."""

from __future__ import annotations

import math
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx

# Кафе «Адам», село Октябрьский, 41 (карта на сайте)
DEFAULT_CAFE_LAT = 56.840966
DEFAULT_CAFE_LON = 53.315866


def cafe_coordinates() -> tuple[float, float]:
    lat = float(os.getenv("CAFE_LAT", str(DEFAULT_CAFE_LAT)))
    lon = float(os.getenv("CAFE_LON", str(DEFAULT_CAFE_LON)))
    return lat, lon


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def geocode_address(address: str) -> tuple[float, float] | None:
    cleaned = " ".join(address.strip().split())
    if len(cleaned) < 8:
        return None

    yandex_key = (os.getenv("YANDEX_GEOCODER_API_KEY") or "").strip()
    if yandex_key:
        coords = await _geocode_yandex(cleaned, yandex_key)
        if coords:
            return coords

    return await _geocode_nominatim(cleaned)


async def _geocode_yandex(address: str, api_key: str) -> tuple[float, float] | None:
    query = f"Удмуртия, {address}"
    url = "https://geocode-maps.yandex.ru/v1/"
    params = {"apikey": api_key, "geocode": query, "format": "json", "lang": "ru_RU", "results": 1}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception:
        return None

    members = (data.get("response") or {}).get("GeoObjectCollection", {}).get("featureMember") or []
    if not members:
        return None
    pos = members[0].get("GeoObject", {}).get("Point", {}).get("pos", "")
    if not pos:
        return None
    try:
        lon_str, lat_str = pos.split()
        return float(lat_str), float(lon_str)
    except (ValueError, TypeError):
        return None


async def _geocode_nominatim(address: str) -> tuple[float, float] | None:
    query = f"{address}, Удмуртия, Россия"
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1, "countrycodes": "ru"}
    headers = {"User-Agent": "AdamCafeDelivery/1.0 (kafeadam.ru)"}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            items = response.json()
    except Exception:
        return None

    if not items:
        return None
    try:
        return float(items[0]["lat"]), float(items[0]["lon"])
    except (KeyError, TypeError, ValueError):
        return None


def delivery_fee_rub(
    subtotal: Decimal,
    distance_km: float,
    free_delivery_threshold: Decimal,
    price_per_km: Decimal,
) -> Decimal:
    if subtotal >= free_delivery_threshold:
        return Decimal("0.00")
    if distance_km <= 0:
        return Decimal("0.00")
    km_billable = max(1, math.ceil(distance_km))
    fee = (Decimal(km_billable) * price_per_km).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return fee


async def estimate_delivery(
    address: str,
    subtotal: Decimal,
    free_delivery_threshold: Decimal,
    price_per_km: Decimal,
) -> dict[str, Any]:
    coords = await geocode_address(address)
    if coords is None:
        return {
            "ok": False,
            "error": "Не удалось определить адрес. Укажите улицу, дом и город (например: Ижевск, ул. Пушкинская, 10).",
        }

    cafe_lat, cafe_lon = cafe_coordinates()
    lat, lon = coords
    distance_km = haversine_km(cafe_lat, cafe_lon, lat, lon)
    distance_km = round(distance_km, 1)

    fee = delivery_fee_rub(subtotal, distance_km, free_delivery_threshold, price_per_km)
    free = subtotal >= free_delivery_threshold

    return {
        "ok": True,
        "distance_km": distance_km,
        "delivery_fee": float(fee),
        "free_delivery": free,
        "free_delivery_threshold": float(free_delivery_threshold),
        "price_per_km": float(price_per_km),
        "subtotal": float(subtotal),
        "total_with_delivery": float((subtotal + fee).quantize(Decimal("0.01"))),
    }
