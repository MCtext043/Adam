"""SEO: LocalBusiness, Open Graph, IndexNow."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

CAFE_NAME = 'Кафе «Адам»'
CAFE_NAME_PLAIN = "Кафе Адам"
CAFE_STREET = "село Октябрьский, 41"
CAFE_LOCALITY = "село Октябрьский"
CAFE_REGION = "Удмуртская Республика"
CAFE_AREA = "Завьяловский район"
CAFE_COUNTRY = "RU"
CAFE_POSTAL = "426075"
CAFE_LAT = 56.840966
CAFE_LON = 53.315866
DEFAULT_PHONE = "+79524098888"
DEFAULT_PHONE_DISPLAY = "+7 (952) 409-88-88"
YANDEX_MAPS_ORG = "https://yandex.ru/maps/org/adam/1084526191"
LOGO_PATH = "/static/img/adam-logo.png"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip().strip('"').strip("'")


def site_url() -> str:
    base = (_env("PUBLIC_BASE_URL") or "https://kafeadam.ru").rstrip("/")
    if base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        return "https://" + base.removeprefix("http://")
    return base


def cafe_phone() -> str:
    return _env("CAFE_PHONE", DEFAULT_PHONE)


def cafe_phone_display() -> str:
    raw = cafe_phone()
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 11 and digits.startswith("7"):
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return raw or DEFAULT_PHONE_DISPLAY


def cafe_phone_href() -> str:
    digits = "".join(c for c in cafe_phone() if c.isdigit())
    if not digits:
        digits = DEFAULT_PHONE.lstrip("+").replace(" ", "")
    if not digits.startswith("7") and len(digits) == 10:
        digits = "7" + digits
    return f"tel:+{digits}"


def yandex_metrika_id() -> str:
    return _env("YANDEX_METRIKA_ID")


def indexnow_key() -> str:
    return _env("INDEXNOW_KEY")


def og_image_url() -> str:
    custom = _env("OG_IMAGE_URL")
    return custom or f"{site_url()}{LOGO_PATH}"


def local_business_json_ld(*, page_url: str, page_name: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Restaurant",
        "@id": f"{site_url()}/#restaurant",
        "name": CAFE_NAME_PLAIN,
        "alternateName": CAFE_NAME,
        "url": site_url(),
        "image": og_image_url(),
        "telephone": cafe_phone(),
        "priceRange": "₽₽",
        "servesCuisine": ["Кавказская", "Русская", "Выпечка"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": CAFE_STREET,
            "addressLocality": CAFE_LOCALITY,
            "addressRegion": CAFE_REGION,
            "postalCode": CAFE_POSTAL,
            "addressCountry": CAFE_COUNTRY,
        },
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": CAFE_LAT,
            "longitude": CAFE_LON,
        },
        "areaServed": [
            {"@type": "City", "name": "Ижевск"},
            {"@type": "Place", "name": CAFE_LOCALITY},
            {"@type": "AdministrativeArea", "name": CAFE_AREA},
        ],
        "hasMenu": f"{site_url()}/#menu",
        "acceptsReservations": False,
        "potentialAction": {
            "@type": "OrderAction",
            "target": f"{site_url()}/#menu",
            "name": "Заказать доставку",
        },
    }
    vk_url = _env("CAFE_VK_URL")
    same_as = [YANDEX_MAPS_ORG]
    if vk_url:
        same_as.insert(0, vk_url)
    data["sameAs"] = same_as
    if page_name:
        data["mainEntityOfPage"] = {"@type": "WebPage", "@id": page_url, "name": page_name}
    return data


def breadcrumb_json_ld(items: list[tuple[str, str]]) -> dict[str, Any]:
    elements = []
    for pos, (name, url) in enumerate(items, start=1):
        elements.append(
            {
                "@type": "ListItem",
                "position": pos,
                "name": name,
                "item": url,
            }
        )
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": elements,
    }


def json_ld_script(*schemas: dict[str, Any]) -> str:
    if len(schemas) == 1:
        payload = schemas[0]
    else:
        payload = {"@context": "https://schema.org", "@graph": list(schemas)}
    return json.dumps(payload, ensure_ascii=False)


def indexnow_urls() -> list[str]:
    base = site_url()
    return [base + path if path != "/" else base + "/" for path in ("/", "/about")]


async def ping_indexnow() -> None:
    key = indexnow_key()
    if not key:
        return
    host = site_url().removeprefix("https://").removeprefix("http://").rstrip("/")
    body = {
        "host": host,
        "key": key,
        "keyLocation": f"{site_url()}/{key}.txt",
        "urlList": indexnow_urls(),
    }
    endpoints = (
        "https://yandex.com/indexnow",
        "https://api.indexnow.org/indexnow",
    )
    async with httpx.AsyncClient(timeout=15.0) as client:
        for endpoint in endpoints:
            try:
                await client.post(endpoint, json=body)
            except Exception:
                pass


def ping_indexnow_sync() -> None:
    key = indexnow_key()
    if not key:
        return
    host = site_url().removeprefix("https://").removeprefix("http://").rstrip("/")
    body = {
        "host": host,
        "key": key,
        "keyLocation": f"{site_url()}/{key}.txt",
        "urlList": indexnow_urls(),
    }
    endpoints = (
        "https://yandex.com/indexnow",
        "https://api.indexnow.org/indexnow",
    )
    with httpx.Client(timeout=15.0) as client:
        for endpoint in endpoints:
            try:
                client.post(endpoint, json=body)
            except Exception:
                pass
