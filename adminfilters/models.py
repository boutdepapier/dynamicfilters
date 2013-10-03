import simplejson

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext as _

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

BOOLEAN_FIELD_CHOICES = (
     ('true', _(u'true')), 
     ('false', _(u'False'))
)

class CustomFilter(models.Model):
    """Model which stores filter set. """
    
    name = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User)
    path_info = models.CharField(max_length=255)
    model_name = models.CharField(max_length=255)
    app_name = models.CharField(max_length=255)
    default = models.BooleanField(default=False)
    ordering = models.CharField(max_length=255)

    @property
    def model(self):
        """Dynamically importing application model."""
        
        module = __import__('%s.models' % self.app_name, fromlist=['models'])
        model = getattr(module, self.model_name, None)
        return model

    @property
    def all_fields(self):
        """Getting list of all fields from imported model."""
        
        return self.model._meta.fields + self.model._meta.local_many_to_many
    
    @property
    def choices(self):
        """List of fields, available for attaching to filter set. Already attached fields and primary key are excluded."""
        
        return [(f.name, f.verbose_name.capitalize()) for f in self.all_fields if f.name not in self.columns and not f.primary_key]

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
        for query in self.queries.all():
            key = query.field
            if query.criteria:  # avoiding load of empty criteria
                if query.criteria.startswith('_not'):
                    key += '__%s' % query.criteria[4:]
                elif query.criteria not in ['today', 'this_week', 'this_month', 'this_year', 'between', 'days_ago']:
                    key += '__%s' % query.criteria
                elif len(query.field_value) > 1 or query.criteria == 'days_ago':
                    key += '__in'
                
                # preparing date-related criterias
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
                    filter_params[key] = query.field_value
        return filter_params, exclude_params

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
        
        if (isinstance(self.model_field, models.CharField) or isinstance(self.model_field, models.IntegerField)) \
                                                                            and getattr(self.model_field, 'choices', None):
            return [(str(c[0]), c[1]) for c in self.model_field.choices]
        
        if isinstance(self.model_field, (models.fields.related.ForeignKey, models.fields.related.ManyToManyField)):
            fk_ids = [fk_id[0] for fk_id in self.model.objects.values_list('%s__id' % self.field).annotate() if fk_id[0]]
            kwargs = {'id__in': fk_ids}
            fk_models = self.model_field.related.parent_model.objects.filter(**kwargs)
            return [(m.id, unicode(m)) for m in fk_models]
        
        if isinstance(self.model_field, models.BooleanField):
            return BOOLEAN_FIELD_CHOICES
        return
    
    @property
    def model(self):
        """Dynamically importing application model."""
        
        module = __import__('%s.models' % self.custom_filter.app_name, fromlist=['models'])
        model = getattr(module, self.custom_filter.model_name, None)
        return model
    
    @property
    def model_field(self):
        model_field = self.model._meta.get_field_by_name(self.field)[0]
        return model_field
    
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

@receiver(post_save, sender=CustomFilter)
def filter_updater(sender, instance, **kwargs):
    if not instance.path_info:
        instance.path_info = '/admin/%s/%s/' % (instance.app_name, instance.model_name.lower())
        instance.save()