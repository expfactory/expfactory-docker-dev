import collections
import operator
import os

from expdj.settings import STATIC_ROOT,BASE_DIR,MEDIA_ROOT,MEDIA_URL

from guardian.shortcuts import assign_perm, get_users_with_perms, remove_perm
from jsonfield import JSONField
from polymorphic.models import PolymorphicModel

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, DO_NOTHING
from django.db.models.signals import m2m_changed

media_dir = os.path.join(BASE_DIR,MEDIA_ROOT)

class Battery(models.Model):
    '''A battery is a collection of experiment templates'''

    ORDER_CHOICES = (
        ("random", "random"),
        ("specified", "specified"),
    )

    # Name must be unique because anonymous link is generated from hash
    name = models.CharField(max_length=200, unique=True, null=False, verbose_name="Name of battery")
    email = models.EmailField(verbose_name="Email database",blank=False,null=False,
                              help_text="All data is sent to a Gmail account, for use as a database. The current limit is 1000/user/month.")
    description = models.TextField(blank=True, null=True)
    consent = models.TextField(blank=True, null=True,help_text="Use HTML syntax to give your consent formatting.")
    advertisement = models.TextField(blank=True, null=True,help_text="Use HTML syntax to give your advertisement formatting.")
    instructions = models.TextField(blank=True, null=True,help_text="Use HTML syntax to give your instructions formatting.")
    owner = models.ForeignKey(User)
    contributors = models.ManyToManyField(User,related_name="battery_contributors",related_query_name="contributor", blank=True,help_text="Select other Experiment Factory users to add as contributes to the battery.  Contributors can edit and deploy the battery.",verbose_name="Contributors")
    add_date = models.DateTimeField('date published', auto_now_add=True)
    modify_date = models.DateTimeField('date modified', auto_now=True)
    maximum_time = models.IntegerField(help_text="Maximum number of minutes for the battery to endure.", null=True, verbose_name="Maxiumum time", blank=True)
    active = models.BooleanField(choices=((False, 'Inactive'),
                                          (True, 'Active')),
                                           default=True,verbose_name="Active")
    presentation_order = models.CharField("order function for presentation of experiments",max_length=200,choices=ORDER_CHOICES,default="random",help_text="Select experiments randomly, or in a custom specified order.")
    required_batteries = models.ManyToManyField(
        "Battery",
        blank=True,
        related_name='required_batteries_mtm',
        help_text=("Batteries which must be completed for this battery to be "
                  "attempted")
    )
    restricted_batteries = models.ManyToManyField(
        "Battery",
        blank=True,
        related_name='restricted_batteries_mtm',
        help_text=("Batteries that must not be completed in order for "
                   "this battery to be attempted")
    )
    private = models.BooleanField(choices=((False, 'Public'),
                                           (True, 'Private')),
                                            default=False,verbose_name="Private")

    def get_install_dir(self):
        '''get_install_dir returns the battery install directory (with experiment folders)
        on the server.
        '''
        install_dir = "%s/experiments/%s" %(media_dir,self.id)
        return install_dir 

    def get_serve_url(self):
        '''get_serve_url returns the base battery url from which experiment folders 
        are statically served (eg, /static/experiments/[self.id]/[expid]
        '''
        install_url = "%sexperiments/%s" %(MEDIA_URL,self.id)
        return install_url

    def get_router_url(self,experiment_id=None):
        if experiment_id==None:
            # Log an experiment as completed first
            return reverse('battery_router', args=[self.id])
        # Just route to an uncompleted one
        return reverse('battery_router', args=[self.id,experiment_id])

    def get_absolute_url(self):
        return_cid = self.id
        return reverse('battery_details', args=[str(return_cid)])

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        super(Battery, self).save(*args, **kwargs)
        assign_perm('del_battery', self.owner, self)
        assign_perm('edit_battery', self.owner, self)

    class Meta:
        ordering = ["name"]
        app_label = 'experiments'
        permissions = (
            ('del_battery', 'Delete battery'),
            ('edit_battery', 'Edit battery')
        )


class Experiment(models.Model):
    '''an experiment is an isolated folder with files to be chosen and customized by researchers into Experiments, and deployed in batteries
    fields correspond with a subset in the config.json
    '''
    exp_id = models.CharField(max_length=200, null=False, blank=False)
    name = models.CharField(max_length=500,help_text="name of the experiment",unique=True)
    time = models.IntegerField()
    reference = models.CharField(max_length=500,help_text="reference or paper associated with the experiment",unique=False)
    template = models.CharField(max_length=100,null=True,blank=False)
    order = models.IntegerField(help_text="Order for experiment presentation. Smaller numbers will be selected first, and equivalent numbers will be chosen from randomly.", null=False, default=1,verbose_name="Experiment order", blank=False)
    version = models.CharField(max_length=100,null=True,blank=False)
    battery = models.ForeignKey(Battery,null=False,blank=False)

    def __meta__(self):
        ordering = ["name"]
        unique_together = (("battery", "exp_id"),)

    def __str__(self):
        return self.name

    # Get the installation directory of an experiment
    def get_install_dir(self):
        return "%s/%s" %(self.battery.get_install_dir(),self.exp_id)

    def serve_url(self):
        battery_url = self.battery.get_serve_url()
        return "%s/%s/" %(battery_url,self.exp_id)

    # Get the url for an experiment
    def get_absolute_url(self):
        return_cid = self.id
        return reverse('experiment_details', args=[str(return_cid)])


def contributors_changed(sender, instance, action, **kwargs):
    if action in ["post_remove", "post_add", "post_clear"]:
        current_contributors = set([user.pk for user in get_users_with_perms(instance)])
        new_contributors = set([user.pk for user in [instance.owner, ] + list(instance.contributors.all())])

        for contributor in list(new_contributors - current_contributors):
            contributor = User.objects.get(pk=contributor)
            assign_perm('edit_battery', contributor, instance)

        for contributor in (current_contributors - new_contributors):
            contributor = User.objects.get(pk=contributor)
            remove_perm('edit_battery', contributor, instance)

m2m_changed.connect(contributors_changed, sender=Battery.contributors.through)
