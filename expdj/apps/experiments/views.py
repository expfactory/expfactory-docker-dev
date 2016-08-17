import datetime
import csv
import hashlib
import json
import numpy
import os
import pandas
import pickle
import re
import shutil
import uuid

from expfactory.battery import get_load_static, get_experiment_run
from expfactory.survey import generate_survey
from expfactory.experiment import load_experiment
from expfactory.views import embed_experiment

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms.models import model_to_dict
from django.http import HttpResponse, JsonResponse
from django.http.response import (
    HttpResponseRedirect, HttpResponseForbidden, Http404
)
from django.shortcuts import (
    get_object_or_404, render_to_response, render, redirect
)
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect, csrf_exempt

from expdj.apps.experiments.utils import (
    install_experiments, select_experiments
)
from expdj.apps.main.views import google_auth_view
from expdj.apps.experiments.forms import (
    ExperimentForm, BatteryForm
)
from expdj.apps.experiments.models import (
    Experiment, Battery
)
from expdj.apps.result.models import get_worker
from expdj.apps.result.utils import ( 
    get_worker_experiments,  complete_survey_result, zip_up
)
from expdj.apps.result.tasks import check_battery_dependencies, send_result

from expdj.settings import BASE_DIR,STATIC_ROOT,MEDIA_ROOT,DOMAIN_NAME
import expdj.settings as settings
from expdj.apps.users.models import User


media_dir = os.path.join(BASE_DIR,MEDIA_ROOT)

### AUTHENTICATION ####################################################

def check_experiment_edit_permission(request):
    if request.user.is_superuser:
        return True
    return False

def check_battery_create_permission(request):
    if not request.user.is_anonymous():
        if request.user.is_superuser:
            return True

    user_roles = User.objects.filter(user=request.user)
    if len(user_roles) == 0:
        return False
    elif user_roles[0].role in ["LOCAL"]:
        return True
    return False

def check_battery_delete_permission(request,battery):
    if not request.user.is_anonymous():
        if request.user == battery.owner:
            return True
        if request.user.is_superuser:
            return True
    return False

def check_battery_edit_permission(request,battery):
    if not request.user.is_anonymous():
        if request.user == battery.owner or request.user in battery.contributors.all():
            return True
        if request.user.is_superuser:
            return True
    return False



#### EXPERIMENTS #############################################################

# get experiment
def get_experiment(eid,request):
    keyargs = {'id':eid}
    try:
        experiment = Experiment.objects.get(**keyargs)
    except Experiment.DoesNotExist:
        raise Http404
    else:
        return experiment

# All experiments for the user
def experiments_view(request):
    experiments = Experiment.objects.filter(battery__private=False)
    context = {'experiments': experiments}
    return render(request, 'experiments/all_experiments.html', context)


# Preview and Serving ----------------------------------------------------------

def preview_experiment(request,eid):
    experiment = get_experiment_template(eid,request)
    experiment_type = get_experiment_type(experiment)
    experiment_folder = os.path.join(media_dir,experiment_type,experiment.exp_id)
    template = '%s/%s_preview.html' %(experiment_type,experiment_type[:-1])
    experiment_html = embed_experiment(experiment_folder,url_prefix="/")
    context = {"preview_html":experiment_html}
    return render_to_response(template, context)


# Experiments ----------------------------------------------------------

@login_required
def edit_experiment(request,bid,eid):
    '''edit_experiment
    view to edit experiment already added to battery
    '''
    battery = get_battery(bid,request)
    experiment = get_experiment(eid,request)

    if request.method == "POST":
        form = ExperimentForm(request.POST, instance=experiment)

        if form.is_valid():
            experiment = form.save(commit=False)
            experiment.save()
            for cc in experiment.credit_conditions.all():
                update_credits(experiment,cc.id)
            return HttpResponseRedirect(battery.get_absolute_url())
    else:
        form = ExperimentForm(instance=experiment)

    context = {"form": form,
               "experiment":experiment,
               "battery":battery}
    return render(request, "experiments/edit_experiment.html", context)


@login_required
def save_experiment(request,bid):
    '''save_experiment
    save experiment and custom details for battery. This is linked to the upload experiment view,
    as experiments come by way of upload (from Github url)
    '''
    battery = get_battery(bid,request)

    if request.method == "POST":
        contenders = request.POST.keys()
        
        # Get the repo_url and requests experiments
        repo_url = request.POST.get("repo_url",None)
        expression = re.compile("^EXPERIMENT_")
        experiment_ids = [x.replace("EXPERIMENT_","") for x in contenders if expression.search(x)]
        
        if repo_url != None and len(experiment_ids)>0:
            message = install_experiments(battery,repo_url,experiment_ids)    
        return view_battery(request,bid,message=message)

    return HttpResponseRedirect(battery.get_absolute_url())


@login_required
def upload_experiment(request,bid):
    '''upload_experiment
    By default, show experiments available in expfactory-experiments, expfactory-surverys, and expfactory-games
    '''
    battery = get_battery(bid,request)
    context = {"bid":battery.id}
    return render(request, "experiments/upload_experiment.html", context)
    

@login_required
def change_experiment_order(request,bid,eid):
    '''change_experiment_order changes the ordering of experiment presentation.
    Any integer value is allowed, and duplicate values means that experiments will
    the equivalent number will be selected from randomly.
    :param bid: the battery id
    :param eid: the experiment id
    '''
    experiment = get_experiment(eid,request)
    battery = get_battery(bid,request)
    can_edit = check_experiment_edit_permission(request)
    if request.method == "POST":
        if can_edit:
            if "order" in request.POST:
                new_order = request.POST["order"]
                if new_order != "":
                    experiment.order = int(new_order)
                    experiment.save()

    return HttpResponseRedirect(battery.get_absolute_url())


@login_required
def remove_experiment(request,bid,eid):
   '''remove_experiment
   removes an experiment from a battery
   '''
   battery = get_battery(bid,request)
   experiment = get_experiment(eid,request)
   if check_battery_edit_permission(request,battery):
       battery_dir = battery.get_install_dir()
       experiment_dir = "%s/%s" %(battery_dir,experiment.id)
       if os.path.exists(experiment_dir):
           shutil.rmtree(experiment_dir) 
       experiment.delete()
   return HttpResponseRedirect(battery.get_absolute_url())


@login_required
def download_experiment(request,eid):
    '''download_experiment downloads an experiment folder for the user
    :param eid: the experiment id 
    '''
    experiment = get_experiment(eid,request)
    if check_battery_edit_permission(request,experiment.battery):
        zipped = zip_up(experiment)
        zip_name = "%s_%s" %(experiment.exp_id,experiment.id)
        response = HttpResponse(zipped.getvalue(), content_type="application/x-zip-compressed")
        response['Content-Disposition'] = 'attachment; filename=%s' % zip_name
        return response
    return HttpResponseRedirect(experiment.battery.get_absolute_url())
        

### BATTERIES #########################################################

# get battery with experiments
def get_battery(bid,request):
    keyargs = {'pk':bid}
    try:
        battery = Battery.objects.get(**keyargs)
    except Battery.DoesNotExist:
        raise Http404
    else:
        return battery


# View a battery
@login_required
def view_battery(request, bid,message=None):
    battery = get_battery(bid,request)

    # Generate anonymous link
    anon_link = "%s/batteries/%s/%s/anon" %(DOMAIN_NAME,bid,hashlib.md5(battery.name).hexdigest())

    # Generate gmail auth link
    gmail_link = "%s/batteries/%s/%s/auth" %(DOMAIN_NAME,bid,hashlib.md5(battery.name).hexdigest())

    # Determine permissions for edit and deletion
    edit_permission = check_battery_edit_permission(request,battery)
    delete_permission = check_battery_edit_permission(request,battery)
    experiments = Experiment.objects.filter(battery=battery)

    context = {'battery': battery,
               'edit_permission':edit_permission,
               'delete_permission':delete_permission,
               'anon_link':anon_link,
               'gmail_link':gmail_link,
               'experiments':experiments}

    if message != None:
        context['message'] = message

    return render(request,'batteries/battery_details.html', context)


# Show all batteries, or user batteries
@login_required
def batteries_view(request,uid=None):
    if uid != None:
        batteries = Battery.objects.filter(owner_id=uid)
        title = "My Batteries"
    else:
        batteries = Battery.objects.filter(private=False)
        title = "All Batteries"

    context = {"batteries":batteries,
               "title":title}

    return render(request, 'batteries/all_batteries.html', context)


# Errors and Messages ----------------------------------------------------------
def enable_cookie_view(request):
    '''enable_cookie_view alerts user cookies not enabled
    '''
    return render_to_response("experiments/cookie_sorry.html")


def get_battery_intro(battery,show_advertisement=True):

    instruction_forms = []

    # !Important: title for consent instructions must be "Consent" - see instructions_modal.html if you change
    if show_advertisement == True:
        if battery.advertisement != None: instruction_forms.append({"title":"Advertisement","html":battery.advertisement})
    if battery.consent != None: instruction_forms.append({"title":"Consent","html":battery.consent})
    if battery.instructions != None: instruction_forms.append({"title":"Instructions","html":battery.instructions})
    return instruction_forms


def serve_battery_anon(request,bid,keyid):
    '''serve an anonymous local battery, userid is generated upon going to link
    '''
    # Check if the keyid is correct
    battery = get_battery(bid,request)
    uid = hashlib.md5(battery.name).hexdigest()

    if uid == keyid:

        # If the user has already started and authenticated
        # NEED TO CHECK THIS WITH PICKLE - not sure why they chose False
        userid = request.session.get('worker_id', None)
        if userid == None:
            userid = uuid.uuid4()
            worker = get_worker(userid,create=True)
            request.session['worker_id'] = worker.id
        
        return redirect("intro_battery",bid=bid,userid=userid)

    # Invalid URL for battery!
    else:
        return render_to_response("messages/robot_sorry.html")


@csrf_protect
def serve_battery_gmail(request,bid):
    '''serves a battery, creating user with gmail'''
    # Check if the keyid is correct
    battery = get_battery(bid,request)
    uid = hashlib.md5(battery.name).hexdigest()
    if "keyid" in request.POST and "gmail" in request.POST:
        keyid = request.POST["keyid"]
        address = request.POST["gmail"]
        if uid==keyid:
            userid = hashlib.md5(address).hexdigest()
            worker = get_worker(userid,create=True)
            return redirect("intro_battery",bid=bid,userid=userid)
        else:
            return render_to_response("messages/robot_sorry.html")
    else:
        return render_to_response("messages/robot_sorry.html")


def preview_battery(request,bid):

    # No robots allowed!
    if request.user_agent.is_bot:
        return render_to_response("messages/robot_sorry.html")

    if request.user_agent.is_pc:

        battery = get_battery(bid,request)
        context = {"instruction_forms":get_battery_intro(battery),
                   "start_url":"/batteries/%s/dummy" %(bid),
                   "assignment_id":"assenav tahcos"}

        return render(request, "experiments/serve_battery_intro.html", context)


def intro_battery(request,bid,userid=None):
    '''intro_battery is where the user can read the instructions, advertisement, etc.,
    and choose to start the battery (or not)
    '''
    # No robots allowed!
    if request.user_agent.is_bot:
        return render_to_response("messages/robot_sorry.html")

    # Humans are ok :)
    if request.user_agent.is_pc:

        if userid == None:
            # The user can only continue if was directed from the correct link (serve_battery_anon)
            # that generated the session
            userid = request.session.get('worker_id', None)
            if userid == None:
                return render_to_response("messages/robot_sorry.html")

        # The userid will be sent to the browser and saved via a service worker
        battery = get_battery(bid,request)
        router_url = battery.get_router_url()

        # We set the userid in the template to send to the service worker before routing to battery
        context = {"instruction_forms":get_battery_intro(battery),
                   "start_url":router_url,
                   "userid":userid}

        return render(request, "batteries/serve_battery_intro.html", context)


@login_required
def dummy_battery(request,bid):
    '''dummy_battery lets the user run a faux battery (preview)'''

    battery = get_battery(bid,request)
    deployment = "docker-local"

    # Does the worker have experiments remaining?
    task_list = select_experiments(battery,uncompleted_experiments=battery.experiments.all())
    experimentTemplate = ExperimentTemplate.objects.filter(exp_id=task_list[0].template.exp_id)[0]
    experiment_type = get_experiment_type(experimentTemplate)
    task_list = battery.experiments.filter(template=experimentTemplate)
    result = None
    context = {"worker_id": "Dummy Worker"}
    if experiment_type in ["games","surveys"]:
        template = "%s/serve_battery_preview.html" %(experiment_type)
    else:
        template = "%s/serve_battery.html" %(experiment_type)

    return deploy_battery(deployment="docker-preview",
                          battery=battery,
                          experiment_type=experiment_type,
                          context=context,
                          task_list=task_list,
                          template=template,
                          result=result)

# Route the user to the next experiment
@csrf_exempt
def battery_router(request,bid,eid=None):
    '''battery_router will direct the user (determined from the session variable) to an uncompleted experiment. If an
    experiment id is provided, the redirect is being sent from a completed experiment, and we log the experiment as completed
    first. 
    '''
    # No robots allowed!
    if request.user_agent.is_bot:
        return render_to_response("messages/robot_sorry.html")

    # Is this a valid user?
    userid = request.session.get('worker_id', None)
    if userid == None:
        return render_to_response("messages/invalid_id_sorry.html")
    worker = get_worker(userid)

    # Retrieve the battery based on the bid
    battery = get_battery(bid,request)

    # If there is a post, we are finishing an experiment and sending data
    if request.method == "POST" and eid != None:

        experiment = get_experiment(eid,request)
   
        # If it's a survey, format the results before sending
        if experiment.template == "survey":
            data = request.POST
            data = complete_survey_result(experiment,data)
        
        # Mark the experiment as completed    
        if experiment not in worker.experiments_completed.all():

            # Only send data if the user hasn't completed it yet
            send_result.apply_async([experiment.id,worker.id,data])
            worker.experiments_completed.add(experiment)
            worker.save()

    # Deploy the next experiment
    missing_batteries, blocking_batteries = check_battery_dependencies(battery, worker)
    if missing_batteries or blocking_batteries:
        return render_to_response(
            "messages/battery_requirements_not_met.html",
            context={'missing_batteries': missing_batteries,
                     'blocking_batteries': blocking_batteries}
        )

    # Is the battery still active?
    if battery.active == False:
        context = {"contact_email":battery.email}
        return render(request, "messages/battery_inactive.html", context)

    # Does the worker have experiments remaining?
    uncompleted_experiments = get_worker_experiments(worker,battery)
    experiments_left = len(uncompleted_experiments)
    if experiments_left == 0:
        # Thank you for your participation - no more experiments!
        return render_to_response("messages/worker_sorry.html")

    next_experiment = select_experiments(battery,uncompleted_experiments)[0]
    
    # Redirect the user to the experiment!
    return HttpResponseRedirect(next_experiment.serve_url())


@login_required
def add_battery(request):
    '''add_battery
    Function for adding new battery to database
    '''
    return redirect('batteries')


@login_required
def edit_battery(request, bid=None):

    battery_permission = check_battery_create_permission(request)

    if battery_permission == True:
        header_text = "Add new battery"
        if bid:
            battery = get_battery(bid,request)
            is_owner = battery.owner == request.user
            header_text = battery.name
            battery_edit_permission = check_battery_edit_permission(request,battery)
            if battery_edit_permission == False:
                return HttpResponseForbidden()
        else:
            is_owner = True
            battery = Battery(owner=request.user)
            battery_edit_permission = True
        if request.method == "POST":
            if is_owner:
                form = BatteryForm(request.POST,instance=battery)
            if form.is_valid():
                previous_contribs = set()
                if form.instance.pk is not None:
                    previous_contribs = set(form.instance.contributors.all())
                    message = "Battery updated successfully."
                else:
                    # If it's a new battery, we need to submit a form to formspree
                    message = """Battery created successfully! After installing experiments, we reccommend 
                                 that you test your battery before making it live. An unsuccessful attempt 
                                 to send data to your email using the SendGrid API will deactive your battery."""

                battery = form.save(commit=False)
                battery.save()

                if is_owner:
                    form.save_m2m()  # save contributors
                    current_contribs = set(battery.contributors.all())
                    new_contribs = list(current_contribs.difference(previous_contribs))

                return view_battery(request,battery.id,message=message)

        else:
            if is_owner:
                form = BatteryForm(instance=battery)
            else:
                form = BatteryForm(instance=battery)

        context = {"form": form,
                   "is_owner": is_owner,
                   "header_text":header_text,
                   "battery_edit_permission":battery_edit_permission}

        return render(request, "experiments/edit_battery.html", context)
    else:
        return redirect("batteries")


# Delete a battery
@login_required
def delete_battery(request, bid):
    battery = get_battery(bid,request)
    delete_permission = check_battery_delete_permission(request,battery)
    if delete_permission==True:
        install_dir = battery.get_install_dir()
        # Delete associated experiments
        [e.delete() for e in battery.experiment_set.all()]
        if os.path.exists(install_dir):
            shutil.rmtree(install_dir)
        battery.delete()
    return redirect('batteries')
