"""
scheduler_tags.py - Custom template tags for timetable grid rendering
"""

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get item from dict by key. Usage: {{ dict|get_item:key }}"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.simple_tag
def get_day_period(grid, day, period):
    """
    Return entries for a given day and period from the timetable grid.
    Usage: {% get_day_period grid day period as cell_entries %}
    """
    return grid.get(day, {}).get(period, [])
