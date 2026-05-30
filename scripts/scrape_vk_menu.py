"""Scrape VK community market catalog into data/vk_menu.json."""

from __future__ import annotations

import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from playwright.sync_api import Response, sync_playwright

GROUP_ID = 235109594
CATALOG_URL = f"https://vk.ru/market-{GROUP_ID}?screen=group"
ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data" / "vk_menu.json"
CLIENT_ID = "6287487"
API_VERSION = "5.276"


def best_photo_url(photo: dict[str, Any] | None) -> str:
    if not photo:
        return ""
    sizes = photo.get("sizes") or []
    if sizes:
        return max(sizes, key=lambda s: (s.get("width") or 0) * (s.get("height") or 0))["url"]
    for key in ("photo_604", "photo_256", "photo_130", "photo_75"):
        if photo.get(key):
            return photo[key]
    return ""


def upgrade_image_url(url: str) -> str:
    if "size=0x400" in url:
        return url.replace("size=0x400", "size=604x604")
    return url


def price_from_item(item: dict[str, Any]) -> Decimal:
    amount = item.get("price", {}).get("amount")
    if amount is not None:
        return Decimal(str(amount)) / Decimal("100")
    text = item.get("price", {}).get("text") or ""
    digits = re.sub(r"[^\d]", "", text)
    return Decimal(digits or "0")


def normalize_item(raw: dict[str, Any], category: str = "Меню") -> dict[str, Any]:
    name = (raw.get("title") or raw.get("name") or "").strip()
    description = (raw.get("description") or "").strip() or name
    thumb = raw.get("thumb_photo") or best_photo_url(raw.get("thumb") or raw.get("photos", [{}])[0] if raw.get("photos") else raw.get("photo"))
    if not thumb and raw.get("photos"):
        thumb = best_photo_url(raw["photos"][0])
    image_url = upgrade_image_url(thumb) if thumb else ""
    return {
        "vk_id": raw.get("id"),
        "name": name,
        "description": description[:2000],
        "price": str(price_from_item(raw)),
        "category": category or "Меню",
        "image_url": image_url,
    }


def collect_from_storefront(payload: dict[str, Any], bucket: dict[int, dict[str, Any]]) -> None:
    response = payload.get("response") or {}
    for block in response.get("catalog", {}).get("sections", []) or []:
        section_name = (block.get("title") or block.get("name") or "Меню").strip()
        for item in block.get("items") or []:
            if item.get("id"):
                bucket[item["id"]] = normalize_item(item, section_name)
    for item in response.get("items") or []:
        if item.get("id"):
            bucket[item["id"]] = normalize_item(item)
    for item in response.get("market_items") or []:
        if item.get("id"):
            bucket[item["id"]] = normalize_item(item)


def scrape() -> list[dict[str, Any]]:
    items: dict[int, dict[str, Any]] = {}
    product_urls: set[str] = set()

    def on_response(response: Response) -> None:
        url = response.url
        if response.status != 200:
            return
        if "method/market." not in url:
            return
        try:
            payload = response.json()
        except Exception:
            return
        if "error" in payload:
            return
        if "getStorefront" in url or "market.get" in url:
            collect_from_storefront(payload, items)
        if "getById" in url:
            item = (payload.get("response") or {}).get("item")
            if item and item.get("id"):
                items[item["id"]] = normalize_item(item, items.get(item["id"], {}).get("category", "Меню"))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ru-RU",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.on("response", on_response)
        page.goto(CATALOG_URL, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(3000)

        for _ in range(25):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(700)

        hrefs = page.eval_on_selector_all(
            'a[href*="/market/product/"]',
            "els => [...new Set(els.map(e => e.getAttribute('href')).filter(Boolean))]",
        )
        for href in hrefs:
            product_urls.add(urljoin("https://vk.ru", href))

        # Fetch descriptions for items missing text
        for url in sorted(product_urls):
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(1200)

        browser.close()

    result = [item for item in items.values() if is_real_product(item)]
    result.sort(key=lambda x: x["name"].lower())
    if not result and product_urls:
        raise RuntimeError("No API items captured; VK may have blocked headless access.")
    return result


def is_real_product(item: dict[str, Any]) -> bool:
    vk_id = item.get("vk_id") or 0
    price = Decimal(item.get("price") or "0")
    return vk_id > 1_000_000 and price > 0 and bool(item.get("image_url"))


def main() -> None:
    products = scrape()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(products)} products to {OUT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
