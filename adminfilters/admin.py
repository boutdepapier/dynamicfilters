import json

from django.conf import settings
from django.conf.urls import patterns, url
from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.core import urlresolvers
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render_to_response, redirect
from django.template import RequestContext

from models import CustomFilter, CustomQuery, CustomBundledQuery
from forms import CustomFilterForm, AddCustomFilterForm

ADMINFILTERS_ADD_PARAM = getattr(settings, 'ADMINFILTERS_ADD_PARAM', 'add_adminfilters')
ADMINFILTERS_LOAD_PARAM = getattr(settings, 'ADMINFILTERS_LOAD_PARAM', 'load_adminfilters')
ADMINFILTERS_SAVE_PARAM = getattr(settings, 'ADMINFILTERS_SAVE_PARAM', 'save_adminfilters')
ADMINFILTERS_CREATE_FILTERS = getattr(settings, 'ADMINFILTERS_CREATE_FILTERS', False)


class CustomChangeList(ChangeList):
    """Customized class for extending filters loading."""
    
    def get_filters(self, request):
        if not request.session.get('use_new_filters'):
            return super(CustomChangeList, self).get_filters(request)
        self.current_filter = CustomFilter.objects.filter(user=request.user, path_info=request.path_info, default=True)
        
        # loading filter set params into change list, so they will be applied in queryset
        if self.current_filter:
            filter_params, self.exclude_params, self.bundled_params = self.current_filter[0].get_filter_params()
            self.params.update(**filter_params)
        f = super(CustomChangeList, self).get_filters(request)
        return f

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
                # if there're no pre-defined fields, adding first available field so filter set won't be empty
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
        # if request.session.get('use_new_filters'):
        return CustomChangeList
        # return super(CustomFiltersAdmin, self).get_changelist(request, **kwargs)

    
    def add_new_filter(self, request):
        """Controller for adding new filter set. On successful save, user will be redirected back to changelist controller."""
        
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
                if not '_addanother' in request.POST:
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
