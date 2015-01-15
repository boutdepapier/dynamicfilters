import json

from django.conf import settings
from django.conf.urls import patterns, url
from django.contrib import admin
from django.contrib.admin.filters import FieldListFilter
from django.contrib.admin.views.main import ChangeList, IGNORED_PARAMS
from django.core import urlresolvers
from django.core.exceptions import SuspiciousOperation
from django.db import models
from django.db.models.fields import FieldDoesNotExist
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render_to_response, redirect
from django.template import RequestContext
from django.utils.encoding import smart_str
from django.contrib.admin.util import get_fields_from_path, lookup_needs_distinct, prepare_lookup_value

from models import CustomFilter, CustomQuery, CustomBundledQuery
from forms import CustomFilterForm, AddCustomFilterForm

ADMINFILTERS_ADD_PARAM = getattr(settings, 'ADMINFILTERS_ADD_PARAM', 'add_adminfilters')
ADMINFILTERS_LOAD_PARAM = getattr(settings, 'ADMINFILTERS_LOAD_PARAM', 'load_adminfilters')
ADMINFILTERS_SAVE_PARAM = getattr(settings, 'ADMINFILTERS_SAVE_PARAM', 'save_adminfilters')
ADMINFILTERS_CREATE_FILTERS = getattr(settings, 'ADMINFILTERS_CREATE_FILTERS', False)


class CustomChangeList(ChangeList):
    """Customized class for extending filters loading."""
    current_filter = None
    
    def get_filters(self, request):
        if not request.session.get('use_new_filters'):
            return super(CustomChangeList, self).get_filters(request)

        new_filter, created = CustomFilter.objects.get_or_create(user=request.user, model_name=self.model.__name__, app_name=self.model._meta.app_label, default=True)
        form = CustomFilterForm(request.GET.copy(), custom_filter=new_filter)
        if len(request.GET) and form.is_valid():
            form.save()

        self.current_filter = CustomFilter.objects.filter(user=request.user, path_info=request.path_info, default=True)
        
        # loading filter set params into change list, so they will be applied in queryset
        if self.current_filter:
            filter_params, self.exclude_params, self.bundled_params = self.current_filter[0].get_filter_params()
            self.params.update(**filter_params)

        lookup_params = self.params.copy() # a dictionary of the query string
        use_distinct = False

        # Remove all the parameters that are globally and systematically
        # ignored.
        for ignored in IGNORED_PARAMS:
            if ignored in lookup_params:
                del lookup_params[ignored]

        # Normalize the types of keys
        for key, value in lookup_params.items():
            if not isinstance(key, str):
                # 'key' will be used as a keyword argument later, so Python
                # requires it to be a string.
                del lookup_params[key]
                lookup_params[smart_str(key)] = value

            if not self.model_admin.lookup_allowed(key, value):
                raise SuspiciousOperation("Filtering by %s not allowed" % key)

        filter_specs = []
        if self.list_filter:
            for list_filter in self.list_filter:
                if callable(list_filter):
                    # This is simply a custom list filter class.
                    spec = list_filter(request, lookup_params,
                        self.model, self.model_admin)
                else:
                    field_path = None
                    if isinstance(list_filter, (tuple, list)):
                        # This is a custom FieldListFilter class for a given field.
                        field, field_list_filter_class = list_filter
                    else:
                        # This is simply a field name, so use the default
                        # FieldListFilter class that has been registered for
                        # the type of the given field.
                        field, field_list_filter_class = list_filter, FieldListFilter.create
                    if not isinstance(field, models.Field):
                        field_path = field
                        field = get_fields_from_path(self.model, field_path)[-1]
                    spec = field_list_filter_class(field, request, lookup_params,
                        self.model, self.model_admin, field_path=field_path)
                    # Check if we need to use distinct()
                    use_distinct = (use_distinct or
                                    lookup_needs_distinct(self.lookup_opts,
                                                          field_path))
                if spec and spec.has_output():
                    filter_specs.append(spec)

        # At this point, all the parameters used by the various ListFilters
        # have been removed from lookup_params, which now only contains other
        # parameters passed via the query string. We now loop through the
        # remaining parameters both to ensure that all the parameters are valid
        # fields and to determine if at least one of them needs distinct(). If
        # the lookup parameters aren't real fields, then bail out.

        for key, value in lookup_params.items():
            lookup_params[key] = prepare_lookup_value(key, value)
            try:
                use_distinct = (use_distinct or lookup_needs_distinct(self.lookup_opts, key))
            except FieldDoesNotExist, e:
                lookup_params.pop(key)
                # raise IncorrectLookupParameters(e)
        return filter_specs, bool(filter_specs), lookup_params, use_distinct

        # CustomFilter.objects.all().delete()
        # return f

    def get_query_set(self, request):

        qs = super(CustomChangeList, self).get_query_set(request)
        try:
            qs = qs.exclude(**self.exclude_params)
        except:
            pass
        try:
            for query in self.current_filter[0].bundled_queries.all():
                query_instance = query.query_instance(request, self.bundled_params,
                                                      self.current_filter.model, self.model_admin)
                updated_qs = query_instance.queryset(request, qs)
                if updated_qs:
                    qs = updated_qs
        except:
            pass
        return qs


class CustomFiltersAdmin(admin.ModelAdmin):

    class Media:
        js = ('/static/admin/js/admin/DateTimeShortcuts.js',
              '/static/admin/js/calendar.js',
              '/static/admin/js/jquery.init.js',
              '/static/admin/js/jquery.js',
              '/static/adminfilters/js/jquery_rebind.js',
              '/static/adminfilters/js/jquery.cookie.js',
              '/static/adminfilters/js/jquery.form.js',
              '/static/adminfilters/js/adminfilters.js')
        
        css = {
               'all': ('/static/adminfilters/css/adminfilters.css',)
        }
    
    def changelist_view(self, request, *args, **kwargs):
        if not request.session.get('use_new_filters'):
            return super(CustomFiltersAdmin, self).changelist_view(request, *args, **kwargs)

        if not getattr(self, 'default_list_filter', None):
            self.default_list_filter = self.list_filter
        
        # Checking if default filter set was created for current application and model, for current user.
        # Otherwise, creating one. Eventually, there's at least one set of filters for application model per each user.
        new_filter, created = CustomFilter.objects.get_or_create(user=request.user, model_name=self.model.__name__, 
                                                                 app_name=self.model._meta.app_label, default=True)
        # once custom filter set has been created, adding fields from list_filter setting to current filter set
        if ADMINFILTERS_CREATE_FILTERS and created:
            for field in self.default_list_filter:
                # since custom list_filters are not supported for now, limiting filterset criteria to fields only
                if isinstance(field, (str, unicode)):
                    CustomQuery.objects.get_or_create(custom_filter=new_filter, field=field)
                else:
                    query = CustomBundledQuery.objects.get_or_create(custom_filter=new_filter, module_name=field.__module__,
                                                             class_name=field.__name__)[0]
                    query_instance = query.query_instance(None, {}, self.model, None)
                    query.field = query_instance.parameter_name
                    query.save()
            else:
                # if there are no pre-defined fields, adding first available field so filter set won't be empty
                CustomQuery.objects.create(custom_filter=new_filter, field=new_filter.choices[0][0])

        # disabling right sidebar with filters by setting empty list_filter setting
        self.list_filter = []

        # overriding default ordering
        if new_filter.filter_ordering:
            self.ordering = new_filter.filter_ordering
        return super(CustomFiltersAdmin, self).changelist_view(request, *args, **kwargs)

    def lookup_allowed(self, *args, **kwargs):
        return True
    
    def get_changelist(self, request, **kwargs):
        use_new_filters = request.GET.get('use_new_filters')
        if use_new_filters:
            if use_new_filters == 'true':
                request.session['use_new_filters'] = True
            elif use_new_filters == 'false':
                request.session['use_new_filters'] = False
                if getattr(self, 'default_list_filter', None):
                    self.list_filter = self.default_list_filter
            request.GET._mutable = True
            request.GET.pop('use_new_filters')
            request.GET._mutable = False

        """Extending change list class for loading custom filters."""
        return CustomChangeList
    
    def add_new_filter(self, request):
        """
        Controller for adding new filter set.
        On successful save, user will be redirected back to changelist controller.
        """
        
        # creating temporary filter set, it's available to attach field until it's saved
        current_filter, created = CustomFilter.objects.get_or_create(user=request.user, app_name=self.opts.app_label, 
                                                                     model_name=self.model.__name__, 
                                                                     default=False, name='temporary')
        form = AddCustomFilterForm(custom_filter=current_filter)
        if request.method == 'POST':
            form = AddCustomFilterForm(request.POST, custom_filter=current_filter)
            new_query = form.data.get(ADMINFILTERS_ADD_PARAM, None)
            if new_query:
                form = CustomFilterForm(request.POST.copy(), custom_filter=current_filter, new_query=new_query)
                return render_to_response('custom_filter_form.html', {'form': form}, context_instance=RequestContext(request))
            elif form.is_valid():
                form.save()
                if '_addanother' not in request.POST:
                    return redirect(urlresolvers.reverse('admin:%s_%s_changelist' % (self.opts.app_label, self.opts.module_name)))
                
                # clearing form if user wants to add one more filter set
                form = AddCustomFilterForm(custom_filter=current_filter)

        context = {'presets': CustomFilter.get_filters(user=request.user,
                                                       path_info=request.path_info),
                   'current_filter': current_filter,
                   'is_popup': False,
                   'opts': self.model._meta,
                   'change': False,
                   'save_as': True,
                   'has_delete_permission': False,
                   'has_add_permission': True,
                   'add': True,
                   'has_change_permission': False,
                   'media': self.media,
                   'form': form,
                   'add_param': ADMINFILTERS_ADD_PARAM}
        return render_to_response('admin_filter_edit.html', context, context_instance=RequestContext(request))
    
    def save_filter(self, request):
        """
        Dedicated controller for saving filter set and its settings. 
        """
        new_query = request.GET.get(ADMINFILTERS_ADD_PARAM, None)
        load_preset = request.GET.get(ADMINFILTERS_LOAD_PARAM, None)
        save_filter = request.GET.get(ADMINFILTERS_SAVE_PARAM, None)
        data = {'success': True}

        if load_preset:
            CustomFilter.objects.filter(user=request.user, model_name=self.model.__name__, 
                                        app_name=self.model._meta.app_label).update(default=False)
            CustomFilter.objects.filter(id=load_preset).update(default=True)
        
        new_filter = CustomFilter.objects.get(user=request.user, model_name=self.model.__name__, 
                                              app_name=self.model._meta.app_label, default=True)
        if new_query:
            form = CustomFilterForm(request.GET.copy(), custom_filter=new_filter, new_query=new_query)
            return render_to_response('custom_filter_form.html', {'form': form}, context_instance=RequestContext(request))

        if save_filter:
            form = CustomFilterForm(request.GET.copy(), custom_filter=new_filter)
            if form.is_valid():
                form.save()
            else:
                response = render_to_response('custom_filter_form.html', {'form': form}, 
                                              context_instance=RequestContext(request))
                data.update(response=response, success=False)
        return HttpResponse(json.dumps(data), content_type='application/json')
    
    def delete_filter(self, request, filter_id):
        """Deleting custom filter and redirecting back to change list. User allowed to delete own filters only."""
        
        custom_filter = get_object_or_404(CustomFilter, id=filter_id, user=request.user)
        custom_filter.delete()
        return redirect(urlresolvers.reverse('admin:%s_%s_changelist' % (self.opts.app_label, self.opts.module_name)))
    
    def clear_filter(self, request):
        current_filter = CustomFilter.objects.filter(user=request.user, model_name=self.model.__name__, 
                                                     app_name=self.model._meta.app_label, default=True)
        if current_filter:
            current_filter[0].delete()
        return redirect(urlresolvers.reverse('admin:%s_%s_changelist' % (self.opts.app_label, self.opts.module_name)))
    
    def get_urls(self):
        """Extending current ModelAdmin's urlconf."""
        
        urls = super(CustomFiltersAdmin, self).get_urls()
        options = (self.opts.app_label, self.opts.module_name)
        custom_urls = patterns('',
            url(r'^add_filter/$', self.add_new_filter, name='%s_%s_add_filter' % options),
            url(r'^save_filter/$', self.save_filter, name='%s_%s_save_filter' % options),
            url(r'^delete_filter/(\d+)/$', self.delete_filter, name='%s_%s_delete_filter' % options),
            url(r'^clear_filter/$', self.clear_filter, name='%s_%s_clear_filter' % options),
        )
        
        return custom_urls + urls
