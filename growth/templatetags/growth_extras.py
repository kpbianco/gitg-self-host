from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def percentage(value, digits=0) -> str:
    if value is None:
        return "—"
    try:
        number = Decimal(str(value)) * 100
        return f"{number:.{int(digits)}f}%"
    except (InvalidOperation, TypeError, ValueError):
        return "—"
