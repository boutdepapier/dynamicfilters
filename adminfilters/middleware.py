from django.conf import settings
from django.template.loader import render_to_string
from models import CustomFilter
from forms import CustomFilterForm

ADMINFILTERS_ADD_PARAM = getattr(settings, 'ADMINFILTERS_ADD_PARAM', 'add_adminfilters')
ADMINFILTERS_LOAD_PARAM = getattr(settings, 'ADMINFILTERS_LOAD_PARAM', 'load_adminfilters')
ADMINFILTERS_HEADER_TAG = getattr(settings, 'ADMINFILTERS_HEADER_TAG', '<div class="module" id="changelist">')
ADMINFILTERS_SAVE_PARAM = getattr(settings, 'ADMINFILTERS_SAVE_PARAM', 'save_adminfilters')

class CustomFiltersMiddleware(object):
    """Middleware for loading current default filter set and rendering it."""
    
    def process_response(self, request, response):
        if getattr(request, 'user', None) and request.user.is_authenticated():
            current_filter = CustomFilter.objects.filter(user=request.user, path_info=request.path_info, default=True)
            if current_filter:
                custom_filters = CustomFilter.get_filters(user=request.user, path_info=request.path_info)
                form = CustomFilterForm(custom_filter=current_filter[0],
                                        custom_filters=custom_filters)
                content = render_to_string('header.html', {'form': form,
                                                           'current_filter': current_filter[0],
                                                           'opts': current_filter[0].model._meta,
                                                           'add_param': ADMINFILTERS_ADD_PARAM,
                                                           'load_param': ADMINFILTERS_LOAD_PARAM,
                                                           'save_param': ADMINFILTERS_SAVE_PARAM})
                response.content = response.content.replace(ADMINFILTERS_HEADER_TAG, 
                                                            ADMINFILTERS_HEADER_TAG + content.encode('utf-8'))
        return response