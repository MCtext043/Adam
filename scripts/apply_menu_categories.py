"""Назначить категории всем позициям в data/vk_menu.json."""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.menu_categories import categorize_menu_item

MENU_PATH = ROOT / "data" / "vk_menu.json"


def main() -> None:
    items = json.loads(MENU_PATH.read_text(encoding="utf-8"))
    counts: Counter[str] = Counter()
    for item in items:
        item["category"] = categorize_menu_item(
            item.get("name", ""),
            item.get("description", ""),
        )
        counts[item["category"]] += 1

    MENU_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {len(items)} items in {MENU_PATH}")
    for category, n in sorted(counts.items()):
        print(f"  {category}: {n}")


if __name__ == "__main__":
    main()
