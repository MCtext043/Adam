"""Проверка подключения к API ЭЛПЛАТ (createQr)."""

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_env_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()

from app.elplat import create_dynamic_qr, elplat_config, elplat_ready, public_base_url


async def main() -> None:
    if not elplat_ready():
        print("FAIL: задайте в .env (в корне проекта):")
        print("  ELPLAT_ENABLED=true")
        print("  ELPLAT_LOGIN=...")
        print("  ELPLAT_PASSWORD=...")
        print("  ELPLAT_ORG_ID=...")
        print("  PUBLIC_BASE_URL=http://kafeadam.ru")
        print("")
        print("Затем: pip install -r requirements.txt")
        sys.exit(1)

    cfg = elplat_config()
    callback = f"{public_base_url()}/api/payments/elplat/callback?order_id=0"
    print(f"API: {cfg['api_url']}")
    print(f"Login: {cfg['login']}, orgId: {cfg['org_id']}")
    print(f"Callback: {callback}")

    try:
        info = await create_dynamic_qr(
            amount_rub=Decimal("1.00"),
            payment_purpose="Test Adam Cafe",
            callback_url=callback,
            redirect_url=f"{public_base_url()}/",
        )
    except Exception as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)

    print("OK: QR создан")
    print(f"  qrcId: {info.get('qrcId')}")
    print(f"  qrData: {info.get('qrData')}")


if __name__ == "__main__":
    asyncio.run(main())
