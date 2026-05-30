"""Import data/vk_menu.json into the database (same logic as app startup)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import import_vk_products, load_vk_menu_items, startup_session


def main() -> None:
    items = load_vk_menu_items()
    if not items:
        raise SystemExit("No valid items in data/vk_menu.json — run scripts/scrape_vk_menu.py first.")
    with startup_session() as session:
        changes = import_vk_products(session)
    print(f"Imported {len(items)} VK menu items ({changes} changes).")


if __name__ == "__main__":
    main()
