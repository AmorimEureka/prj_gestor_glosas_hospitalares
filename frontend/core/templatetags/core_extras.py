from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter
def api_date(value):
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")

    text = str(value).strip()
    if not text:
        return "-"

    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).strftime("%d/%m/%Y")
    except ValueError:
        pass

    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return text[:10]

    return text


@register.filter
def br_currency(value):
    if value in (None, ""):
        value = 0

    text = str(value).strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".")

    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return value

    formatted = f"{number:,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")
