from django import template
from django.conf import settings
from django.core.urlresolvers import reverse

register = template.Library()

ADMINFILTERS_URLCONF = getattr(settings, 'ADMINFILTERS_URLCONF', None)

@register.filter
def get_field(value, arg):
    if arg in value.fields:
        return value[arg]
    return ''

@register.filter
def get_label(value, arg):
    field = value.fields.get(arg, None)
    return field.label if field else ''

@register.filter
def get_field_errors(value, arg):
    if value._errors:
        return value._errors.get(arg, None)
    return ''

@register.filter
def get_container_name(value):
    return value[0:value.find('_')]

@register.filter
def get_container_name(value):
    return value[0:value.find('_')]

@register.filter
def delete_filter_url(value, arg):
    return reverse('admin:%s_%s_%s' % (value.app_label, value.module_name, 'delete_filter'), ADMINFILTERS_URLCONF, args=(arg,))

@register.filter
def save_filter_url(value):
    return reverse('admin:%s_%s_%s' % (value.app_label, value.module_name, 'save_filter'), ADMINFILTERS_URLCONF)