"""Apply cafe price list to data/vk_menu.json."""
import json
from pathlib import Path

PRICES: dict[str, int] = {
    "Шашлык из баранины": 650,
    "Антрекот из баранины": 1100,
    "Антрекот из свинины": 590,
    "Куриное филе": 450,
    "Куриные крылышки": 430,
    "Люля - кебаб из курицы": 490,
    "Люля - кебаб из баранины": 590,
    "Люля - кебаб смешаный": 560,
    "Семга на мангале": 1150,
    "Дорадо на мангале": 1050,
    "Скумбрия с молодым картофелем": 600,
    "Карп с молодым картофелем": 830,
    "Плов по - узбекски": 530,
    "Жаренные хинкали": 120,
    "Жаренные хинкали с говядиной": 120,
    "Хинкали": 120,
    "Хинкали с говядиной": 120,
    "Пельмени жареные": 360,
    "Пельмени отварные": 360,
    "Чебуреки с говядиной": 320,
    "Чебуреки": 310,
    "Лаваш": 150,
    "Пицца пепперони": 590,
    "Пицца куриная": 600,
    "Картофель фри": 290,
    "Овощное ассорти": 430,
    "Парус": 460,
    "Оливье с лососем": 420,
    "Греческий": 440,
    "Цезарь": 440,
    "Цезарь с креветками": 570,
    "Салат с рукколой и креветками": 560,
    "Чобан": 550,
    "Теплый салат с баклажаном": 440,
    "Ассорти из солений": 610,
    "Мясное ассорти": 1050,
    "Рыбное ассорти": 990,
    "Креветки": 1050,
    "Сельдь с картофелем": 380,
    "Сыр \"Домашний\"": 320,
    "Сырное ассорти": 990,
    "Лимонная нарезка": 150,
    "Борщ со сметаной": 350,
    "Лагман": 450,
    "Соютма": 580,
    "Ассорти сезонных фруктов": 1050,
    "Рулетики из баклажанов с чесноком и грецким орехом": 390,
    "Филе Миньон": 1300,
    "Долма": 550,
    "Чыхыртма из курицы": 1200,
    "Омлет с помидорами": 310,
}

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "data" / "vk_menu.json"
data = json.loads(path.read_text(encoding="utf-8"))
updated = 0
for item in data:
    price = PRICES.get(item["name"])
    if price is not None:
        item["price"] = str(price)
        updated += 1
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
names_in_json = {item["name"] for item in data}
missing_in_json = sorted(set(PRICES) - names_in_json)
unchanged = sorted(names_in_json - set(PRICES))
print(f"updated {updated} items")
if missing_in_json:
    print("in price list but not in menu json:", missing_in_json)
print(f"unchanged in json ({len(unchanged)}):")
for name in unchanged:
    print(f"  - {name}")
