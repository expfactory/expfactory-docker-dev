from datetime import timedelta, datetime
import json
import os
import requests

from expfactory.battery import get_load_static, get_experiment_run
from numpy.random import choice
from optparse import make_option

from django.contrib.auth.decorators import login_required
from django.core.management.base import BaseCommand
from django.http.response import (HttpResponseRedirect, HttpResponseForbidden,
    HttpResponse, Http404, HttpResponseNotAllowed)
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render_to_response, render, redirect
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from expdj.apps.experiments.models import Battery
from expdj.apps.experiments.views import (check_battery_edit_permission, 
     get_battery_intro)
from expdj.apps.experiments.utils import get_experiment_type, select_experiments
from expdj.apps.result.forms import WorkerContactForm
from expdj.apps.result.models import Worker, get_worker
from expdj.apps.result.tasks import *
from expdj.apps.result.utils import *
from expdj.settings import BASE_DIR,STATIC_ROOT,MEDIA_ROOT

media_dir = os.path.join(BASE_DIR,MEDIA_ROOT)

#### VIEWS ############################################################

def finished_view(request):
    '''finished_view thanks worker for participation, and gives submit button
    '''
    return render_to_response("turk/worker_sorry.html")

def check_battery_view(battery, worker_id):
    missing_batteries, blocking_batteries = check_battery_dependencies(battery, worker_id)
    if missing_batteries or blocking_batteries:
        return render_to_response(
            "turk/battery_requirements_not_met.html",
            context={'missing_batteries': missing_batteries,
                     'blocking_batteries': blocking_batteries}
        )
    else:
        return None
