"""Отправка писем с корректной UTF-8 кодировкой и HTML-оформлением."""

from __future__ import annotations

import os
import re
import smtplib
import ssl
from decimal import Decimal
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any

def parse_smtp_address(raw: str, fallback: str) -> str:
    """Оставляет только email для envelope SMTP (без «Имя <addr>»)."""
    value = (raw or "").strip()
    if not value:
        return fallback
    angle = re.search(r"<([^>]+)>", value)
    if angle:
        return angle.group(1).strip()
    if "@" in value and " " not in value:
        return value
    return fallback


ORDER_STATUS_LABELS = {
    "new": "Новый",
    "cooking": "Готовится",
    "delivering": "В доставке",
    "done": "Готово",
    "cancelled": "Отменён",
}


def _format_money(value: Decimal | float) -> str:
    amount = float(value)
    return f"{amount:,.0f}".replace(",", " ") + " ₽"


def _order_lines_html(order: Any) -> str:
    rows = []
    for item in order.items:
        line_sum = item.price * item.quantity
        rows.append(
            f"""
            <tr>
              <td style="padding:10px 0;border-bottom:1px solid #eee;">{item.product_name}</td>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;">{item.quantity}</td>
              <td style="padding:10px 0;border-bottom:1px solid #eee;text-align:right;">{_format_money(line_sum)}</td>
            </tr>
            """
        )
    return "".join(rows)


def _order_discount_block(order: Any) -> str:
    spent = int(getattr(order, "loyalty_points_spent", 0) or 0)
    if spent <= 0:
        return ""
    return f"""
    <p style="margin:12px 0;color:#75675c;font-size:15px;">
      Списано бонусов: <strong style="color:#201915;">{spent}</strong> (−{_format_money(spent)})
    </p>
    """


def build_order_html(order: Any, *, headline: str, intro_html: str) -> str:
    status_label = ORDER_STATUS_LABELS.get(order.status, order.status)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5eee2;font-family:Georgia,'Times New Roman',serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5eee2;padding:24px 12px;">
    <tr><td align="center">
      <table width="100%" style="max-width:560px;background:#ffffff;border-radius:24px;overflow:hidden;
        border:1px solid rgba(32,25,21,0.1);box-shadow:0 12px 40px rgba(32,25,21,0.08);">
        <tr>
          <td style="background:#201915;color:#f5eee2;padding:28px 24px;text-align:center;">
            <p style="margin:0 0 8px;font-family:Arial,sans-serif;font-size:11px;letter-spacing:0.2em;
              text-transform:uppercase;opacity:0.85;">Кафе «Адам»</p>
            <h1 style="margin:0;font-size:26px;font-weight:500;">{headline}</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 24px;color:#201915;">
            <p style="margin:0 0 16px;font-family:Arial,sans-serif;font-size:16px;line-height:1.6;">{intro_html}</p>
            <p style="margin:0 0 8px;font-family:Arial,sans-serif;font-size:14px;color:#75675c;">
              Заказ №{order.id} · статус: <strong style="color:#201915;">{status_label}</strong>
            </p>
            <table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;font-family:Arial,sans-serif;font-size:15px;">
              <tr style="color:#75675c;font-size:12px;text-transform:uppercase;letter-spacing:0.06em;">
                <th align="left" style="padding-bottom:8px;">Блюдо</th>
                <th style="padding-bottom:8px;">Кол-во</th>
                <th align="right" style="padding-bottom:8px;">Сумма</th>
              </tr>
              {_order_lines_html(order)}
            </table>
            {_order_discount_block(order)}
            <p style="margin:16px 0 0;font-size:22px;font-weight:700;">Итого: {_format_money(order.total)}</p>
            <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
            <p style="margin:0 0 6px;font-family:Arial,sans-serif;font-size:14px;color:#75675c;">
              Телефон: {order.phone}
            </p>
            <p style="margin:0;font-family:Arial,sans-serif;font-size:14px;color:#75675c;">
              Адрес: {order.address}
            </p>
          </td>
        </tr>
        <tr>
          <td style="background:#f5eee2;padding:20px 24px;text-align:center;font-family:Arial,sans-serif;
            font-size:13px;color:#75675c;">
            Спасибо, что выбрали кафе «Адам»!
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def build_order_plain(order: Any, *, intro: str) -> str:
    status_label = ORDER_STATUS_LABELS.get(order.status, order.status)
    lines = [intro, "", f"Заказ №{order.id}. Статус: {status_label}.", "", "Состав:"]
    for item in order.items:
        lines.append(f"— {item.product_name} × {item.quantity} = {_format_money(item.price * item.quantity)}")
    spent = int(getattr(order, "loyalty_points_spent", 0) or 0)
    if spent > 0:
        lines.append(f"Списано бонусов: {spent}")
    lines.extend(
        [
            "",
            f"Итого: {_format_money(order.total)}",
            f"Телефон: {order.phone}",
            f"Адрес: {order.address}",
            "",
            "Кафе «Адам»",
        ]
    )
    return "\n".join(lines)


def send_order_email(order: Any, *, kind: str = "created") -> None:
    to_addr = (order.customer_email or "").strip()
    if not to_addr:
        return

    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    mail_from = parse_smtp_address(os.getenv("SMTP_FROM", ""), user) or user
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
    display_name = os.getenv("SMTP_FROM_NAME", "Кафе Адам").strip()

    if kind == "status":
        status_label = ORDER_STATUS_LABELS.get(order.status, order.status)
        subject = f"Заказ №{order.id}: {status_label}"
        headline = "Статус заказа обновлён"
        intro_html = (
            f"Здравствуйте, {order.customer_name}! "
            f"Ваш заказ №{order.id} — <strong>{status_label}</strong>."
        )
        intro_plain = (
            f"Здравствуйте, {order.customer_name}! "
            f"Ваш заказ №{order.id} — {status_label}."
        )
    else:
        subject = f"Заказ №{order.id} принят"
        headline = "Заказ принят"
        intro_html = (
            f"Здравствуйте, {order.customer_name}! "
            f"Мы получили ваш заказ и передали его на кухню."
        )
        intro_plain = intro_html

    html_body = build_order_html(order, headline=headline, intro_html=intro_html)
    plain_body = build_order_plain(order, intro=intro_plain)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = str(Header(subject, "utf-8"))
    msg["From"] = formataddr((str(Header(display_name, "utf-8")), mail_from))
    msg["To"] = to_addr

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        if use_tls:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.starttls(context=context)
                if user:
                    server.login(user, password)
                server.sendmail(mail_from, [to_addr], msg.as_string())
        else:
            with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as server:
                if user:
                    server.login(user, password)
                server.sendmail(mail_from, [to_addr], msg.as_string())
    except Exception as exc:
        print(f"[email] failed order {order.id} ({kind}): {exc}")
