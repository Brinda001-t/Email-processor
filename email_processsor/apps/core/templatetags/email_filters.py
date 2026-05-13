from django import template
from email.utils import parseaddr

register = template.Library()


@register.filter
def email_only(value):
    _, addr = parseaddr(str(value))
    return addr if addr else value


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
