from django import forms
from django.conf import settings
from django.contrib.admin import widgets  
from django.http import QueryDict
from django.utils.translation import ugettext as _

ADMINFILTERS_ADD_PARAM = getattr(settings, 'ADMINFILTERS_ADD_PARAM', 'add_adminfilters')
ADMINFILTERS_LOAD_PARAM = getattr(settings, 'ADMINFILTERS_LOAD_PARAM', 'load_adminfilters')
ADMINFILTERS_SAVE_PARAM = getattr(settings, 'ADMINFILTERS_SAVE_PARAM', 'save_adminfilters')

class CustomFilterForm(forms.Form):
    """Form for managing filter set."""
    
    ordering = forms.ChoiceField(label=_(u'Order by:'), required=False)
    
    def __init__(self, *args, **kwargs):
        """Preparing form - it consists of dynamic fields, except ordering."""
        
        self.custom_filter = kwargs.pop('custom_filter', None)
        self.custom_filters = kwargs.pop('custom_filters', None)
        super(CustomFilterForm, self).__init__(*args, **kwargs)
        self.skip_validation = True
        self.params = args[0] if args else QueryDict('')
        self.fields['ordering'].choices = [('', '')] + self.custom_filter.ordering_choices
        self.fields['ordering'].initial = self.custom_filter.ordering
        
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
        for query in self.custom_filter.queries.all():
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
                attrs = {'class':'value'}
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
                if query.field_type == 'date':
                    value_field = forms.DateField(initial=query.value, widget=widgets.AdminDateWidget())
                elif query.field_type == 'datetime':
                    value_field = forms.DateTimeField(initial=query.value, widget=widgets.AdminSplitDateTime())
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
                    bvalue = getattr(query, 'field_value', ['',''])
                    self.initial['%s_start' % query.field] = bvalue[0]
                    self.initial['%s_end' % query.field] = bvalue[1]
                    self.initial['%s_dago' % query.field] = ''
                    self.initial['%s_value' % query.field] = ''
            self.field_rows.append(row)

    def save(self, *args, **kwargs):
        params = self.data
        self.custom_filter.ordering = params.get('ordering', None)
        for query in self.custom_filter.queries.all():
            if params.get('%s_enabled' % query.field, None):
                criteria = params.get('%s_criteria' % query.field, 'exact')
                query.criteria = criteria
                value = params.get('%s_value' % query.field, None)
                start = params.get('%s_start' % query.field, None)
                end = params.get('%s_end' % query.field, None)
                days_ago = params.get('%s_dago' % query.field, None)
                if criteria == 'between':
                    query.is_multiple = True
                    query.field_value = [start, end]
                elif criteria == 'days_ago':
                    query.field_value = days_ago
                else:
                    query.is_multiple = True if isinstance(value, list) else False
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
        if self.custom_filter.queries.count() == 0:
            raise forms.ValidationError(_(u'Please add fields to filter set, do not leave it empty.'))
        return super(AddCustomFilterForm, self).clean()
    
    def save(self, *args, **kwargs):
        self.custom_filter.name = self.data['name']
        super(AddCustomFilterForm, self).save(*args, **kwargs)
    
    def __init__(self, *args, **kwargs):
        super(AddCustomFilterForm, self).__init__(*args, **kwargs)
        if not self.params.get(ADMINFILTERS_ADD_PARAM, None):
            self.skip_validation = False
        