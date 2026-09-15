import json

from django import template


register = template.Library()


@register.filter
def get_item(mapping, key):
    return mapping.get(key) if isinstance(mapping, dict) else None


@register.filter
def json_pretty(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


@register.filter
def labelize(value):
    return str(value).replace("_", " ").capitalize()

