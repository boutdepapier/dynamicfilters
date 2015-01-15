from django import forms
from django.conf import settings
from django.contrib.admin import widgets
from django.core.exceptions import ValidationError
from django.forms.fields import DateTimeField
from django.http import QueryDict
from django.utils.translation import ugettext as _

from .models import CustomQuery

ADMINFILTERS_ADD_PARAM = getattr(settings, 'ADMINFILTERS_ADD_PARAM', 'add_adminfilters')
ADMINFILTERS_LOAD_PARAM = getattr(settings, 'ADMINFILTERS_LOAD_PARAM', 'load_adminfilters')
ADMINFILTERS_SAVE_PARAM = getattr(settings, 'ADMINFILTERS_SAVE_PARAM', 'save_adminfilters')


class CustomFilterForm(forms.Form):
    """Form for managing filter set."""
    
    def __init__(self, *args, **kwargs):
        """Preparing form - it consists of dynamic fields, except ordering."""
        
        self.custom_filter = kwargs.pop('custom_filter', None)
        self.custom_filters = kwargs.pop('custom_filters', None)
        self.request = kwargs.pop('request', None)
        self.model_admin = kwargs.pop('model_admin', None)
        self.new_query = kwargs.pop('new_query', None)
        super(CustomFilterForm, self).__init__(*args, **kwargs)
        if type(self.data) == dict:
            self.data = QueryDict(self.data)
        self.skip_validation = True
        self.params = args[0] if args else QueryDict('')
        all_fields = [f.replace('_enabled', '') for f in self.data if f.endswith('_enabled')]
        self.new_fields = [f for f in all_fields if f not in self.custom_filter.all_queries_names]
        if self.new_query:
            self.data['%s_enabled' % self.new_query] = 'on'
            self.new_fields.append(self.new_query)
        
        if isinstance(self.custom_filter.filter_ordering, list):
            ordering_choices = self.custom_filter.ordering_choices
            ordering_field = forms.MultipleChoiceField(required=False)
        else:
            widget = forms.Select(attrs={'class': 'single_ordering'})
            ordering_choices = [('', '')] + self.custom_filter.ordering_choices
            ordering_field = forms.ChoiceField(widget=widget, required=False)
        self.fields['ordering'] = ordering_field
        self.fields['ordering'].choices = ordering_choices
        self.fields['ordering'].initial = self.custom_filter.filter_ordering
        
        if self.custom_filter.choices:
            self.fields[ADMINFILTERS_ADD_PARAM] = forms.ChoiceField(label=_(u'Add field to filter:'), 
                                                                    widget=forms.Select(attrs={'class': 'add_adminfilters'}),
                                                                    required=False)
            self.fields[ADMINFILTERS_ADD_PARAM].choices = [('', '')] + self.custom_filter.choices
        
        if self.custom_filters:
            self.fields[ADMINFILTERS_LOAD_PARAM] = forms.ChoiceField(label=_(u'Load preset:'),
                                                                     widget=forms.Select(attrs={'class':'load_adminfilters'}))
            self.fields[ADMINFILTERS_LOAD_PARAM].choices = [('', '')] + [(cf.id, cf.verbose_name) for cf in self.custom_filters]
        
        self.field_rows = []
        
        for query in self.custom_filter.bundled_queries.all():
            query_instance = query.query_instance(None, {}, self.custom_filter.model, None)
            if query_instance:
                row = ['%s_enabled' % query_instance.parameter_name,
                       '%s_criteria' % query_instance.parameter_name]
                self.fields['%s_enabled' % query_instance.parameter_name] = forms.BooleanField(label=query_instance.title.title(),
                                                                            initial=True,
                                                                            required=False,
                                                                            widget=forms.CheckboxInput(attrs={'class':'enable'}))
                
                query_criterias = [(p, t) for (p, t) in query_instance.lookups(None, self.custom_filter.model)]
                self.fields['%s_criteria' % query_instance.parameter_name] = forms.ChoiceField(choices=query_criterias,
                                                                             initial=query.value,
                                                                             required=False,
                                                                             widget=forms.Select(attrs={'class':'criteria'}))
                self.field_rows.append(row)
        for query in list(self.custom_filter.queries.all()) + self.new_fields:
            if not isinstance(query, CustomQuery):
                query = CustomQuery(custom_filter=self.custom_filter, field=query)
            field = DateTimeField()
            if query.model_field:
                row = ['%s_enabled' % query.field,
                       '%s_criteria' % query.field]
                self.fields['%s_enabled' % query.field] = forms.BooleanField(label=query.field_verbose_name,
                                                                            initial=True,
                                                                            required=False,
                                                                            widget=forms.CheckboxInput(attrs={'class':'enable'}))
                if query.criterias:
                    self.fields['%s_criteria' % query.field] = forms.ChoiceField(choices=query.criterias,
                                                                             initial=query.criteria,
                                                                             required=False,
                                                                             widget=forms.Select(attrs={'class':'criteria'}))
                if query.choices:
                    attrs = {'class': 'value'}
                    if query.is_multiple or len(self.params.getlist('%s_value' % query.field, None)) > 1:
                        widget = forms.SelectMultiple(attrs=attrs)
                        value_field = forms.MultipleChoiceField(choices=query.choices,
                                                    initial=query.value,
                                                    widget=widget)
                    else:
                        widget = forms.Select(attrs=attrs)
                        value_field = forms.ChoiceField(choices=query.choices,
                                                    initial=query.value,
                                                    widget=widget)
                        
                elif query.field_type in ['date', 'datetime']:
                    if query.is_multiple:
                        from datetime import datetime
                        value = datetime.now()
                    else:

                        try:
                            value = field.to_python(query.value)
                        except ValidationError:
                            value = field.to_python(query.value[:-7])
                    if query.field_type == 'date':
                        value_field = forms.DateField(initial=value, widget=widgets.AdminDateWidget())
                    elif query.field_type == 'datetime':
                        value_field = forms.DateTimeField(initial=value, widget=widgets.AdminSplitDateTime())
                    dwidget = forms.TextInput(attrs={'style': 'display: %s' % ('block' if query.criteria == 'days_ago' else 'none'),
                                                     'size': 5})
                    dfield = forms.CharField(initial=query.value, 
                                             widget=dwidget,
                                             required=False)
                else:
                    value_field = forms.CharField(initial=query.value, widget=forms.TextInput(attrs={'size':10}))

                if value_field:
                    self.fields['%s_value' % query.field] = value_field
                    row.append('%s_value' % query.field)
                
                if query.field_type in ['date', 'datetime', 'integer']:
                    row.append('%s_start' % query.field)
                    row.append('%s_end' % query.field)
                    self.fields['%s_start' % query.field] = value_field
                    self.fields['%s_end' % query.field] = value_field
                    if query.field_type in ['date', 'datetime']:
                        row.append('%s_dago' % query.field)
                        self.fields['%s_dago' % query.field] = dfield
                    if query.criteria == 'between':
                        default_value = ['', '']
                        bvalue = getattr(query, 'field_value') or default_value
                        self.initial['%s_start' % query.field] = field.to_python(bvalue[0]) if bvalue[0] else None
                        self.initial['%s_end' % query.field] = field.to_python(bvalue[1]) if bvalue[1] else None
                        self.initial['%s_dago' % query.field] = ''
                        self.initial['%s_value' % query.field] = ''
                self.field_rows.append(row)

    def save(self, *args, **kwargs):
        params = self.data
        if params.get('e'):
            return
        filter_ordering = params.getlist('ordering', None)
        if '' in filter_ordering:
            filter_ordering.remove('')
        self.custom_filter.filter_ordering = filter_ordering
        for query in self.custom_filter.bundled_queries.all():
            query_instance = query.query_instance(None, {}, self.custom_filter.model, None)
            if params.get('%s_enabled' % query_instance.parameter_name, None):
                criteria = params.get('%s_criteria' % query_instance.parameter_name, None)
                query.field = query_instance.parameter_name
                query.value = criteria
                query.save()
            else:
                query.delete()
        for query in list(self.custom_filter.queries.all()) + self.new_fields:
            if not isinstance(query, CustomQuery):
                query = CustomQuery(custom_filter=self.custom_filter, field=query)
            if params.get('%s_enabled' % query.field, None):
                criteria = params.get('%s_criteria' % query.field, 'exact')
                query.criteria = criteria
                value = params.getlist('%s_value' % query.field, None)

                # some sort of hack to detect if we have multiple values
                if not query.is_multiple and not len(value):
                    value = params.get('%s_value' % query.field, None)

                days_ago = params.get('%s_dago' % query.field, None)

                field = DateTimeField()

                if criteria == 'between':
                    start = field.to_python('%s %s' % (params.get('%s_start_0' % query.field, ''), params.get('%s_start_1' % query.field, '')))
                    end = field.to_python('%s %s' % (params.get('%s_end_0' % query.field, ''), params.get('%s_end_1' % query.field, '')))
                    query.is_multiple = True
                    query.field_value = [str(start), str(end)]
                elif criteria == 'days_ago':
                    query.field_value = days_ago
                elif days_ago and not value:
                    query.field_value = field.to_python('%s %s' % (params.get('%s_value_0' % query.field, ''), params.get('%s_value_1' % query.field, '')))
                else:
                    query.is_multiple = True if (isinstance(value, list) and len(value)) else False
                    query.field_value = value
                query.save()
            else:
                query.delete()
        self.custom_filter.save()

    def clean(self):
        if self.skip_validation:
            self._errors = {}
        return super(CustomFilterForm, self).clean()


class AddCustomFilterForm(CustomFilterForm):
    """Form for adding new filter only, not for managing."""
    
    name = forms.CharField(label=_(u'Name:'), required=True,
                           widget=forms.TextInput(attrs={'placeholder': 'New Filter Name', 'size': 40}))
    
    def clean(self):
        params = self.data
        if not filter(lambda x: x.endswith('_enabled'), params.keys()):
            raise forms.ValidationError(_(u'Please add fields to filter set, do not leave it empty.'))
        for q in self.custom_filter.queries.all():
            if not params.get('%s_enabled' % q.field, None):
                del self.fields['%s_enabled' % q.field]
                for suffix in ['criteria', 'value', 'start', 'end', 'dago']:
                    fname = '%s_%s' % (q.field, suffix)
                    if fname in self._errors:
                        del self._errors[fname]
                    if fname in self.fields:
                        del self.fields[fname]
                q.delete()
        return super(AddCustomFilterForm, self).clean()
    
    def save(self, *args, **kwargs):
        self.custom_filter.name = self.data['name']
        super(AddCustomFilterForm, self).save(*args, **kwargs)
    
    def __init__(self, *args, **kwargs):
        super(AddCustomFilterForm, self).__init__(*args, **kwargs)
        if not self.params.get(ADMINFILTERS_ADD_PARAM, None):
            self.skip_validation = False
