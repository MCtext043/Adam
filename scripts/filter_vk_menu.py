"""Re-filter existing data/vk_menu.json without re-scraping."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import VK_MENU_PATH, _is_real_vk_product, _upgrade_vk_image_url

def main() -> None:
    data = json.loads(VK_MENU_PATH.read_text(encoding="utf-8"))
    kept = []
    for raw in data:
        if not _is_real_vk_product(raw):
            continue
        raw["image_url"] = _upgrade_vk_image_url(raw["image_url"])
        kept.append(raw)
    VK_MENU_PATH.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Kept {len(kept)} of {len(data)} items")


if __name__ == "__main__":
    main()
