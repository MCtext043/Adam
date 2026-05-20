"""Проверка send_order_email как при реальном заказе."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

env_path = root / ".env"
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from app.email_service import send_order_email

to = (sys.argv[1] if len(sys.argv) > 1 else "hshbdudgff@gmail.com").strip()
item = SimpleNamespace(product_name="Хачапури по-аджарски", quantity=1, price=460)
order = SimpleNamespace(
    id=9999,
    customer_name="Виктор",
    customer_email=to,
    status="new",
    phone="89512028615",
    address="Репина 35",
    total=460,
    loyalty_points_spent=0,
    items=[item],
)
send_order_email(order, kind="created")
print(f"send_order_email OK -> {to}")
