#!/usr/bin/env python
# -*- coding: utf-8 -*-
from expdj.apps.result.utils import to_dict, get_time_difference
from django.core.validators import MaxValueValidator, MinValueValidator
from expdj.apps.experiments.models import Experiment, ExperimentTemplate, Battery
from expdj.settings import DOMAIN_NAME, BASE_DIR
from django.db.models.signals import pre_init
from django.contrib.auth.models import User
from django.db.models import Q, DO_NOTHING
from django.utils import timezone
from jsonfield import JSONField
from django.db import models
import collections
import datetime

class Worker(models.Model):
    id = models.CharField(primary_key=True, max_length=200, null=False, blank=False)
    session_count = models.PositiveIntegerField(default=0,help_text=("The number of one hour sessions completed by the worker."))
    visit_count = models.PositiveIntegerField(default=0,help_text=("The total number of visits"))
    last_visit_time = models.DateTimeField(null=True,blank=True,help_text=("The date and time, in UTC, the Worker last visited"))

    def __str__(self):
        return "%s" %(self.id)

    def __unicode__(self):
        return "%s" %(self.id)

    class Meta:
        ordering = ['id']



def get_worker(worker_id,create=True):
    '''get a worker
    :param create: update or create
    :param worker_id: the unique identifier for the worker
    '''
    # (<Worker: WORKER_ID: experiments[0]>, True)
    now = timezone.now()

    if create == True:
        worker,_ = Worker.objects.update_or_create(id=worker_id)
    else:
        worker = Worker.objects.filter(id=worker_id)[0]

    if worker.last_visit_time != None: # minutes
        time_difference = get_time_difference(worker.last_visit_time,now)
        # If more than an hour has passed, this is a new session
        if time_difference >= 60.0:
            worker.session_count +=1
    else: # this is the first session
        worker.session_count = 1

    # Update the last visit time to be now
    worker.visit_count +=1
    worker.last_visit_time = now
    worker.save()
    return worker


class Result(models.Model):
    '''A result holds a battery id and an experiment template, to keep track of the battery/experiment combinations that a worker has completed'''
    taskdata = JSONField(null=True,blank=True,load_kwargs={'object_pairs_hook': collections.OrderedDict})
    version = models.CharField(max_length=128,null=True,blank=True,help_text="Experiment version (github commit) at completion time of result")
    worker = models.ForeignKey(Worker,null=False,blank=False,related_name='result_worker')
    experiment = models.ForeignKey(ExperimentTemplate,help_text="The Experiment Template completed by the worker in the battery",null=False,blank=False,on_delete=DO_NOTHING)
    battery = models.ForeignKey(Battery, help_text="Battery of Experiments deployed by the HIT.", verbose_name="Experiment Battery", null=False, blank=False,on_delete=DO_NOTHING)
    finishtime = models.DateTimeField(null=True,blank=True,help_text=("The date and time, in UTC, the Worker finished the result"))
    current_trial = models.PositiveIntegerField(null=True,blank=True,help_text=("The last (current) trial recorded as complete represented in the results."))
    language = models.CharField(max_length=128,null=True,blank=True,help_text="language of the browser associated with the result")
    browser = models.CharField(max_length=128,null=True,blank=True,help_text="browser of the result")
    platform = models.CharField(max_length=128,null=True,blank=True,help_text="platform of the result")
    completed = models.BooleanField(choices=((False, 'Not completed'),
                                             (True, 'Completed')),
                                              default=False,verbose_name="participant completed the experiment")

    class Meta:
        verbose_name = "Result"
        verbose_name_plural = "Results"
        unique_together = ("worker","battery","experiment")

    def __repr__(self):
        return u"Result: id[%s],worker[%s],battery[%s],experiment[%s]" %(self.id,self.worker,self.battery,self.experiment)

    def __unicode__(self):
        return u"Result: id[%s],worker[%s],battery[%s],experiment[%s]" %(self.id,self.worker,self.battery,self.experiment)

    def get_taskdata(self):
        return to_dict(self.taskdata)
