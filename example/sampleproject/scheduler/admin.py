from django.contrib import admin
from adminfilters.admin import CustomFiltersAdmin
from models import Category, Event

class CategoryAdmin(CustomFiltersAdmin):
    list_fields = ('name',)

class EventAdmin(CustomFiltersAdmin):
    list_filter = ('status', 'user')

admin.site.register(Category, CategoryAdmin)
admin.site.register(Event, EventAdmin)