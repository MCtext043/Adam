"""Проверка подключения к API ЭЛПЛАТ (createQr)."""

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.elplat import create_dynamic_qr, elplat_config, elplat_ready, public_base_url


async def main() -> None:
    if not elplat_ready():
        print("FAIL: задайте в .env:")
        print("  ELPLAT_ENABLED=true")
        print("  ELPLAT_LOGIN=...")
        print("  ELPLAT_PASSWORD=...")
        print("  ELPLAT_ORG_ID=...")
        print("  PUBLIC_BASE_URL=http://kafeadam.ru")
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
    print("После теста включите ELPLAT на сервере и задеплойте.")


if __name__ == "__main__":
    asyncio.run(main())
