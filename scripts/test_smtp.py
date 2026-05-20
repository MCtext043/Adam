#!/usr/bin/env python3
"""Проверка SMTP без отправки реального заказа. Запуск:
  python scripts/test_smtp.py
  python scripts/test_smtp.py --send test@example.com
"""
from __future__ import annotations

import argparse
import os
import smtplib
import ssl
import sys
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from app.email_service import parse_smtp_address

# Подхватить .env из корня проекта (локально или в контейнере)
env_path = root / ".env"
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def mask(value: str) -> str:
    if not value:
        return "(пусто)"
    if len(value) <= 4:
        return "****"
    return value[:2] + "****" + value[-2:]


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка SMTP для кафе Адам")
    parser.add_argument("--send", metavar="EMAIL", help="Отправить тестовое письмо на этот адрес")
    args = parser.parse_args()

    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    mail_from = parse_smtp_address(os.getenv("SMTP_FROM", ""), user) or user
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
    from_name = os.getenv("SMTP_FROM_NAME", "Кафе Адам").strip()

    print("=== SMTP config (без пароля) ===")
    print(f"  SMTP_HOST:     {host or '(не задан)'}")
    print(f"  SMTP_PORT:     {port}")
    print(f"  SMTP_USE_TLS:  {use_tls}")
    print(f"  SMTP_USER:     {user or '(не задан)'}")
    print(f"  SMTP_PASSWORD: {mask(password)}")
    print(f"  SMTP_FROM:     {mail_from or '(не задан)'}")
    print(f"  SMTP_FROM_NAME:{from_name}")

    if not host:
        print("\nFAIL: SMTP_HOST не задан — письма отключены (send_order_email сразу выходит).")
        return 1

    if not mail_from:
        print("\nFAIL: нет адреса отправителя (SMTP_FROM или SMTP_USER).")
        return 1

    print("\n=== Подключение к серверу ===")
    context = ssl.create_default_context()
    try:
        if use_tls:
            server = smtplib.SMTP(host, port, timeout=30)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(host, port, timeout=30, context=context)

        with server:
            if user:
                server.login(user, password)
                print("  LOGIN: OK")
            else:
                print("  LOGIN: пропущен (SMTP_USER пустой)")

            if args.send:
                to_addr = args.send.strip()
                msg = MIMEText(
                    "Тестовое письмо от scripts/test_smtp.py.\n"
                    "Если вы видите это — SMTP настроен верно.\n",
                    "plain",
                    "utf-8",
                )
                msg["Subject"] = Header("Тест SMTP — Кафе «Адам»", "utf-8")
                msg["From"] = formataddr((from_name, mail_from))
                msg["To"] = to_addr
                server.sendmail(mail_from, [to_addr], msg.as_string())
                print(f"  SEND: OK -> {to_addr}")
            else:
                print("  SEND: пропущен (укажите --send email@example.com для тестовой отправки)")

    except smtplib.SMTPAuthenticationError as exc:
        print(f"\nFAIL: авторизация SMTP — {exc}")
        print("  Проверьте логин/пароль. Для Yandex нужен пароль приложения.")
        return 2
    except smtplib.SMTPException as exc:
        print(f"\nFAIL: SMTP — {exc}")
        return 3
    except OSError as exc:
        print(f"\nFAIL: сеть — {exc}")
        return 4

    print("\nOK: SMTP доступен.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
