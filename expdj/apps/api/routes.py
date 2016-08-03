import json
import os
import requests

from django.core.management.base import BaseCommand
from django.http import JsonResponse
from django.http.response import (HttpResponseRedirect, HttpResponseForbidden,
    HttpResponse, Http404, HttpResponseNotAllowed)
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render_to_response, render, redirect
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from expdj.apps.api.utils import get_experiment_selection

#### VIEWS ############################################################

def view_repo(request):
    '''view_repo will return a JSON response for all valid experiments in a repo of interest
    '''
    repo_url = request.GET["url"]
    experiments = get_experiment_selection(repo_url)    
    return JsonResponse({"experiments":experiments})
