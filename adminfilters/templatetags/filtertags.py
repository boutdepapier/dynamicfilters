from django import template
from django.conf import settings
from django.core.urlresolvers import reverse

register = template.Library()

ADMINFILTERS_URLCONF = getattr(settings, 'ADMINFILTERS_URLCONF', None)


@register.filter
def get_field(value, arg):
    """Calling arbitrary field from given form"""
    if arg in value.fields:
        return value[arg]
    return ''


@register.filter
def get_label(value, arg):
    """Accessing field label for arbitrary field from given form"""
    field = value.fields.get(arg, '')
    return field.label if field else ''


@register.filter
def get_field_errors(value, arg):
    """Accessing field errors for arbitrary field from given form"""
    if value._errors:
        return value._errors.get(arg, '')
    return ''


@register.filter
def get_container_name(value):
    return value[0:value.rfind('_')]
