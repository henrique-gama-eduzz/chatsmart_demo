from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using a dynamic key."""
    if isinstance(dictionary, dict):
        return dictionary.get(key, "-")
    return "-"

@register.filter
def format_cell_value(value):
    """Format cell value for display."""
    if value is None:
        return "-"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}"
    return str(value)
