import datetime
from django.contrib.auth.models import User
from django.db import models

EVENT_STATUSES = ((0, 'New'),
                  (1, 'In progress'),
                  (2, 'Finished'),)

class Category(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    
    def __unicode__(self):
        return self.name

class Event(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    start = models.DateField(null=True, blank=True)
    end = models.DateField(null=True, blank=True)
    status = models.IntegerField(choices=EVENT_STATUSES, default=0)
    user = models.ForeignKey(User, null=True, blank=True)
    active = models.BooleanField(blank=True, default=True)
    importance = models.IntegerField(null=True, blank=True, default=3)
    created = models.DateTimeField(null=True, blank=True, default=datetime.datetime.now())
    category = models.ManyToManyField(Category, null=True, blank=True)
    
    def __unicode__(self):
        return self.name