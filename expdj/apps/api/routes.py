import json
import os
import requests

from django.core import serializers
from django.core.management.base import BaseCommand
from django.http import JsonResponse
from django.http.response import (HttpResponseRedirect, HttpResponseForbidden,
    HttpResponse, Http404, HttpResponseNotAllowed)
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render_to_response, render, redirect
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from expdj.apps.api.utils import get_experiment_selection
from expdj.apps.experiments.models import Battery, Experiment
from expdj.apps.experiments.views import get_battery, get_experiment

#### VIEWS ############################################################

def view_repo(request):
    '''view_repo will return a JSON response for all valid experiments in a repo of interest
    '''
    repo_url = request.GET["url"]
    experiments = get_experiment_selection(repo_url)    
    return JsonResponse({"experiments":experiments})


def view_battery(request,bid=None):
    '''view_battery will return a JSON response for one or more batteries
    This will eventually need pagination added.
    '''
    # A single battery ID returns associated experiments as well
    if bid != None:
        battery = [get_battery(request,bid)]
        if len(battery) > 0:
            battery = json.loads(serializers.serialize("json",battery,fields=('pk','description','add_date','modify_date','name')))
            experiments = Experiment.objects.filter(battery__id=bid)
            if len(experiments) > 0:
                experiments = json.loads(serializers.serialize("json", experiments,fields=('pk','name','exp_id','version','template',
                                                                                           'time','battery','reference','order')))
            battery[0]['experiments'] = experiments
            return JsonResponse({"results":battery,"count":1})

        # Battery with bid not found!
        else:
            return JsonResponse({"results":[],"count":0,"message":"Battery not found."}) 

    # No bid means return all public batteries information
    else:

        results = Battery.objects.filter(private=False)
        results = serializers.serialize("json", results,fields=('pk','description','add_date','modify_date','name'))
        count = len(results)
        return JsonResponse({"results":results,"count":count})
