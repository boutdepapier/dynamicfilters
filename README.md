# Adminfilters

Adminfilters introduces Redmine-like filters for Django admin application. It allows to plug and configure set of filter to any application model.

## Setup

Examples directory has already configured application.
To enable application, you need to add it to INSTALLED_APPS and 'adminfilters.middleware.CustomFiltersMiddleware' to MIDDLEWARE_CLASSES:

```python
INSTALLED_APPS = (
    ...
    'adminfilters',
)
```

```python
MIDDLEWARE_CLASSES = (
    ...
    'adminfilters.middleware.CustomFiltersMiddleware',
)
```

Also you need to inherit you model admin class from CustomFiltersAdmin, instead of admin.ModelAdmin:

```python
from adminfilters.admin import CustomFiltersAdmin
from models import Category

class CategoryAdmin(CustomFiltersAdmin):
    list_fields = ('name',)
```

## Configuration

`ADMINFILTERS_ADD_PARAM` — parameter for adding new field to existing filters set.
`ADMINFILTERS_LOAD_PARAM` — parameter for loading existing filters set.
`ADMINFILTERS_HEADER_TAG` — HTML tag where rendered filters will be appeneded.
`ADMINFILTERS_SAVE_PARAM` — parameter to indicate save action of filters set for controller.
`ADMINFILTERS_URLCONF` — name of admin application's URLconf.

`ADMINFILTERS_ADD_PARAM`, `ADMINFILTERS_LOAD_PARAM`, `ADMINFILTERS_SAVE_PARAM` are basically fields, that indicate action for filters set management.
They can be configured to avoid collissions with existing form fields or parameters.
