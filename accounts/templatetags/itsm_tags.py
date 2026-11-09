from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """Dictionary lookup for template loops (dict.get is not callable from templates)."""
    return mapping.get(key, key)
