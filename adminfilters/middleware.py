from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from models import CustomFilter
from forms import CustomFilterForm

ADMINFILTERS_ADD_PARAM = getattr(settings, 'ADMINFILTERS_ADD_PARAM', 'add_adminfilters')
ADMINFILTERS_LOAD_PARAM = getattr(settings, 'ADMINFILTERS_LOAD_PARAM', 'load_adminfilters')
ADMINFILTERS_HEADER_TAG = getattr(settings, 'ADMINFILTERS_HEADER_TAG', '<div class="module" id="changelist">')
ADMINFILTERS_SAVE_PARAM = getattr(settings, 'ADMINFILTERS_SAVE_PARAM', 'save_adminfilters')
ADMINFILTERS_URLCONF = getattr(settings, 'ADMINFILTERS_URLCONF', None)

class CustomFiltersMiddleware(object):
    """Middleware for loading current default filter set and rendering it."""
    
    def process_response(self, request, response):
        if 'use_new_filters' in request.META['QUERY_STRING']:
            return redirect(request.path)
        if not request.session.get('use_new_filters'):
            return response

        if getattr(request, 'user', None) and request.user.is_authenticated():
            current_filter = CustomFilter.objects.filter(user=request.user, path_info=request.path_info, default=True)
            if current_filter:
                custom_filters_loaded = True
                try:
                    reverse('admin:%s_%s_%s' % (current_filter[0].model._meta.app_label, 
                                                current_filter[0].model._meta.module_name, 'save_filter'), 
                            ADMINFILTERS_URLCONF)
                except:
                    custom_filters_loaded = False
                if custom_filters_loaded:
                    custom_filters = CustomFilter.get_filters(user=request.user, path_info=request.path_info)
                    form = CustomFilterForm(custom_filter=current_filter[0],
                                            custom_filters=custom_filters)
                    opts = current_filter[0].model._meta
                    urlconf = getattr(request, 'urlconf', ADMINFILTERS_URLCONF)
                    delete_filter_url = reverse('admin:%s_%s_%s' % (opts.app_label, opts.module_name, 'delete_filter'), 
                                                urlconf, args=(current_filter[0].pk,))
                    save_filter_url = reverse('admin:%s_%s_%s' % (opts.app_label, opts.module_name, 'save_filter'), 
                                              urlconf)
                    add_filter_url = reverse('admin:%s_%s_%s' % (opts.app_label, opts.module_name, 'add_filter'), 
                                              urlconf)
                    clear_filter_url = reverse('admin:%s_%s_%s' % (opts.app_label, opts.module_name, 'clear_filter'), 
                                              urlconf)
                    content = render_to_string('header.html', {'form': form,
                                                               'current_filter': opts,
                                                               'opts': current_filter[0].model._meta,
                                                               'add_param': ADMINFILTERS_ADD_PARAM,
                                                               'load_param': ADMINFILTERS_LOAD_PARAM,
                                                               'save_param': ADMINFILTERS_SAVE_PARAM,
                                                               'save_filter_url': save_filter_url,
                                                               'delete_filter_url': delete_filter_url,
                                                               'add_filter_url': add_filter_url,
                                                               'clear_filter_url': clear_filter_url})
                    response.content = response.content.replace(ADMINFILTERS_HEADER_TAG,  ADMINFILTERS_HEADER_TAG + content.encode('utf-8'))
                    if current_filter[0].errors:
                        messages.warning(request, current_filter[0].errors)
        return response
