from django import template

register = template.Library()

@register.filter
def split_pipe(value):
    """Split observations string by ' | ' separator."""
    if not value:
        return []
    return [part.strip() for part in value.split(' | ') if part.strip()]
