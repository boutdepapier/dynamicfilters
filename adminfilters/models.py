import datetime
import simplejson

from django.contrib.auth.models import User
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext as _
from django.db.models.fields.related import ReverseSingleRelatedObjectDescriptor, SingleRelatedObjectDescriptor

EMPTY_CHOICES = [('', ''),]

CHOICE_FIELD_CHOICES = (
    ('exact', _(u'is')), 
    ('not', _(u'is not'))
)

INTEGER_FIELD_CHOICES = (
    ('exact', _(u'is')),
    ('_not', _(u'is not')),
    ('gte', '>='),
    ('gt', '>'), 
    ('lt', '<'),
    ('lte', '<='),
    ('between', _(u'between'))
)

CHAR_FIELD_CHOICES = (
    ('contains', _(u'contains')), 
    ('_notcontains', _(u'doesn\'t contain')), 
    ('startswith', _(u'starts with')),
    ('endswith', _(u'ends with'))
)

DATE_FIELD_CHOICES = (
    ('exact', _(u'equal')),
    ('gt', _(u'later than')),
    ('lt', _(u'before than')),
    ('between', _(u'between')),
    ('today', _(u'today')),
    ('days_ago', _(u'days ago')),
    ('this_week', _(u'this week')),
    ('this_month', _(u'this month')),
    ('this_year', _(u'this year'))
)

FOREIGN_KEY_CHOICES = (
    ('exact', _(u'is')),
    ('isnull', _(u'is null'))
)

BOOLEAN_FIELD_CHOICES = [
     ('true', _(u'true')), 
     ('false', _(u'False'))
]

ADMINFILTERS_URLCONF = getattr(settings, 'ADMINFILTERS_URLCONF', None)

def import_module(app_name):
    django_apps = ('auth',)
    if app_name in django_apps:
        module = __import__('django.contrib.%s.models' % app_name, fromlist=['models'])
    else:
        module = __import__('%s.models' % app_name, fromlist=['models'])
    return module


class CustomFilter(models.Model):
    """Model which stores filter set. """
    
    name = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User)
    path_info = models.CharField(max_length=255)
    model_name = models.CharField(max_length=255)
    app_name = models.CharField(max_length=255)
    default = models.BooleanField(default=False)
    ordering = models.CharField(max_length=255)

    def get_ordering(self):
        if self.ordering:
            try:
                return simplejson.loads(self.ordering)
            except:
                pass
        return self.ordering
    
    def set_ordering(self, value):
        self.ordering = simplejson.dumps(value)
    
    filter_ordering = property(get_ordering, set_ordering)

    @property
    def model(self):
        """Dynamically importing application model."""
        module = import_module(self.app_name)
        model = getattr(module, self.model_name, None)
        return model

    @property
    def all_fields(self):
        """Getting list of all fields from imported model."""
        
        return self.model._meta.fields + self.model._meta.local_many_to_many
    
    @property
    def all_fields_names(self):
        return self.model._meta.get_all_field_names()
    
    @property
    def choices(self):
        """List of fields, available for attaching to filter set. Already attached fields and primary key are excluded."""
        
        return [(f.name, unicode(f.verbose_name).capitalize()) for f in self.all_fields if f.name not in self.columns and not f.primary_key]

    @property
    def ordering_choices(self):
        """List of choices, available for ordering, both descending and ascending."""
        
        choices = []
        for f in self.all_fields:
            choices.append((f.name, f.verbose_name.capitalize() + '(Asc)'))
            choices.append(('-'+str(f.name), f.verbose_name.capitalize() + '(Desc)'))
        return choices

    @property
    def columns(self):
        """List of fields, attached to filter set."""
        
        return [cq.field for cq in self.queries.all()]

    @property
    def all_queries_names(self):
        return [cq.field for cq in self.bundled_queries.all()] + self.columns

    @property
    def verbose_name(self):
        return self.name if self.name else 'default'
    
    @staticmethod
    def get_filters(path_info, user):
        """Getting available non-default filter sets."""
        
        return CustomFilter.objects.filter(path_info__startswith=path_info, user=user, 
                                           default=False).exclude(name='temporary')

    def get_filter_params(self):
        """Preparing parameters for change list queryset, based on attached queries."""
        
        filter_params = {}
        exclude_params = {}
        bundled_params = {}
        for query in self.queries.all():
            if query.model_field:
                key = query.field
                if query.criteria:  # avoiding load of empty criteria
                    if query.criteria.startswith('_not'):
                        key += '__%s' % query.criteria[4:]
                    elif query.criteria not in ['today', 'this_week', 'this_month', 'this_year', 'between', 'days_ago']:
                        key += '__%s' % query.criteria
                    elif len(query.field_value) > 1 or query.criteria == 'days_ago':
                        key += '__in'
                    
                    # preparing date-related criteria
                    if query.criteria in ['today', 'this_week', 'this_month', 'this_year', 'days_ago']:
                        date = datetime.datetime.now()
                        if query.criteria == 'today':
                            value = date.strftime('%Y-%m-%d')
                        if query.criteria == 'this_month':
                            key += '__month'
                            value = date.strftime('%m')
                        if query.criteria == 'this_year':
                            key += '__year'
                            value = date.strftime('%Y')
                            filter_params[key] = value
                        if query.criteria == 'days_ago':
                            filter_params[key] = datetime.date.today() + datetime.timedelta(days=int(query.field_value))
                    elif query.criteria == 'between':
                        filter_params['%s__gt' % key] = query.field_value[0]
                        filter_params['%s__lte' % key] = query.field_value[1]
                    elif query.criteria.startswith('_not'):
                        exclude_params[key] = query.field_value
                    elif query.field_value:     # avoiding load of empty filter value which causes database error
                        if query.model_field.get_internal_type() == 'BooleanField':
                            filter_params[key] = {'true': True, 'false': False}[query.field_value]
                        else:
                            filter_params[key] = query.field_value
        for query in self.bundled_queries.all():
            bundled_params[query.field] = query.value
        return filter_params, exclude_params, bundled_params

    @property
    def errors(self):
        skipped_fields = [f for f in self.columns if f not in self.all_fields_names]
        for f in skipped_fields:
            if '__' in f:
                child_model_name, child_field_name = f.split('__')
                child_model = getattr(self.model, child_model_name)
                if child_model and child_field_name in child_model.related.opts.get_all_field_names():
                    skipped_fields.remove(f)
        if skipped_fields:
            skipped_field_names = ['"%s"' % f for f in skipped_fields]
            return _(u'Fields: %s were skipped in current filterset. They might be renamed or deleted from original model.' % ','.join(skipped_field_names))
        return

class CustomQuery(models.Model):
    """Model which stores fields and settings for every filter set."""
    
    custom_filter = models.ForeignKey(CustomFilter, related_name='queries')
    field = models.CharField(max_length=255)
    criteria = models.CharField(max_length=255, null=True, blank=True)
    is_multiple = models.BooleanField(blank=True, default=False)
    value = models.CharField(max_length=255, null=True, blank=True)
    
    def get_value(self):
        if not self.is_multiple:
            return self.value
        return simplejson.loads(self.value)
    
    def set_value(self, value):
        if not self.is_multiple:
            self.value = value
        else:
            self.value = simplejson.dumps(value)
    
    # Property used for supporting multiple values assignment, provided in lists and dictionaries.
    # Multiple values are used in filter with "between" criteria, which filters values in range of two values.
    field_value = property(get_value, set_value)
    
    @property
    def choices(self):
        """
        Getting list of choices from model fields, which support this. 
        For ForeignKey field it's list of aggregated unique values.
        """
        
        choices = EMPTY_CHOICES if not self.value else []
        
        if (isinstance(self.model_field, models.CharField) or isinstance(self.model_field, models.IntegerField)) \
                                                                            and getattr(self.model_field, 'choices', None):
            field_choices = list(self.model_field.choices)
            return choices + [(str(c[0]), c[1]) for c in field_choices]
        
        if isinstance(self.model_field, (models.fields.related.ForeignKey, models.fields.related.ManyToManyField)):
            fk_ids = [fk_id[0] for fk_id in self.model.objects.values_list('%s__id' % self.field).annotate() if fk_id[0]]
            kwargs = {'id__in': fk_ids}
            fk_models = self.model_field.related.parent_model.objects.filter(**kwargs)
            return choices + [(m.id, unicode(m)) for m in list(fk_models)]
        
        if isinstance(self.model_field, models.BooleanField):
            return choices + BOOLEAN_FIELD_CHOICES
        return
    
    @property
    def model(self):
        """Dynamically importing application model."""
        module = import_module(self.custom_filter.app_name)
        model = getattr(module, self.custom_filter.model_name, None)
        return model
    
    @property
    def child_model(self):
        model_name = self.field.split('__')[0]
        related_instance = getattr(self.model, model_name)
        if related_instance:
            if isinstance(related_instance, ReverseSingleRelatedObjectDescriptor):
                return related_instance.field.related.model
            else:
                return related_instance.related.model
        return
    
    @property
    def model_field(self):
        if '__' in self.field:
            field_name = self.field.split('__')[1]
            
            return self.child_model._meta.get_field_by_name(field_name)[0]
        elif self.field in self.custom_filter.all_fields_names:
            return self.model._meta.get_field_by_name(self.field)[0]
        return
    
    @property
    def field_verbose_name(self):
        return self.model_field.verbose_name.capitalize()
    
    @property
    def criterias(self):
        """Preparing list of criterias for each filter, base on field type."""
        
        if isinstance(self.model_field, models.IntegerField) and getattr(self.model_field, 'choices', None):
            return CHOICE_FIELD_CHOICES
        
        if isinstance(self.model_field, models.IntegerField) and not getattr(self.model_field, 'choices', None):
            return INTEGER_FIELD_CHOICES
        
        elif isinstance(self.model_field, (models.CharField, models.TextField)) and not getattr(self.model_field, 'choices'):
            return CHAR_FIELD_CHOICES

        elif isinstance(self.model_field, (models.DateField, models.DateTimeField)):
            return DATE_FIELD_CHOICES
        
        elif isinstance(self.model_field, (models.fields.related.ForeignKey, models.fields.related.ManyToManyField)):
            return FOREIGN_KEY_CHOICES
        return
    
    @property
    def field_type(self):
        """Identifying field type, based on model field class."""
        
        if not getattr(self.model_field, 'choices', None):
            if isinstance(self.model_field, models.IntegerField):
                return 'integer'
            if isinstance(self.model_field, (models.CharField, models.TextField)):
                return 'char'
            if isinstance(self.model_field, models.DateTimeField):
                return 'datetime'
            if isinstance(self.model_field, models.DateField):
                return 'date'
        return

class CustomBundledQuery(models.Model):
    """Model which stores fields for SimpleListFilter"""
    
    custom_filter = models.ForeignKey(CustomFilter, related_name='bundled_queries')
    module_name = models.CharField(max_length=255, null=True, blank=True)
    class_name = models.CharField(max_length=255, null=True, blank=True)
    field = models.CharField(max_length=255)
    value = models.CharField(max_length=255, null=True, blank=True)

    @property
    def query_instance(self):
        module = __import__(self.module_name, fromlist=[self.module_name])
        if module:
            return getattr(module, self.class_name, None)
        return

@receiver(post_save, sender=CustomFilter)
def filter_updater(sender, instance, **kwargs):
    if not instance.path_info:
        instance.path_info = '/admin/%s/%s/' % (instance.app_name, instance.model_name.lower())
        instance.save()
