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
    install_experiments, select_experiments, generate_new_survey
)
from expdj.apps.main.views import google_auth_view
from expdj.apps.experiments.forms import (
    ExperimentForm, BatteryForm, SurveyForm
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
    experiment = get_experiment(eid,request)
    request.session['no_send'] = "anything"
    return HttpResponseRedirect(experiment.serve_url())


# Experiments ----------------------------------------------------------

def view_experiment(request,eid):
    experiment = get_experiment(eid,request)
    context = {"experiment":experiment}
    return render(request,'experiments/experiment_details.html', context)


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
def new_survey(request,bid):
    '''new_survey generates a new experiment factory survey depending on the users specifications
    '''
    battery = get_battery(bid,request)
    context = {"battery":battery}

    if request.method == "POST":
        context["form"] = SurveyForm(request.POST,request.FILES)
        if context["form"].is_valid():
            file_handle = request.FILES["questions"]
            exp_id = context["form"].cleaned_data['name'].replace(" ","_").lower()
            lookup = context["form"].cleaned_data
            # Ensure that isn't over-writing a current exp_id
            if exp_id not in [e.exp_id for e in battery.experiment_set.all()]:
                # upload the new survey, creating a config.json
                result = generate_new_survey(exp_id=exp_id,
                                            battery=battery,
                                            lookup=lookup,
                                            questions=file_handle)
                # If there is an error, result will not be True
                if result != True:
                    context["message"] = """Error with install: %s""" %(result)
                else: # No error, redirect the user to batteries page
                    return HttpResponseRedirect(battery.get_absolute_url())

            else:
                context["message"] = """An experiment or survey with the exp_id 
                                        %s already exists! Please re-name your survey
                                        and try again.""" %(exp_id)
    else:
        form = SurveyForm()
        context["form"] = form

    return render(request, "surveys/new_survey.html", context)



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
    can_edit = check_battery_edit_permission(request,battery)
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


# Preview ----------------------------------------------------------------------
def preview_battery(request,bid,no_send=None):

    # No robots allowed!
    if request.user_agent.is_bot:
        return render_to_response("messages/robot_sorry.html")

    battery = get_battery(bid,request)
    router_url = battery.get_router_url()

    # If the user has already started and authenticated
    worker = get_worker("DUMMY",create=True)
    request.session['worker_id'] = "DUMMY"
   
    # If no_send is defined, the user doesn't want to email results
    if no_send != None:
       request.session['no_send'] = "anything"

    # We set the userid in the template to send to the service worker before routing to battery
    context = {"instruction_forms":get_battery_intro(battery),
               "start_url":router_url,
               "userid":"DUMMY"}

    return render(request, "batteries/serve_battery_intro.html", context)

def reset_preview(request,bid,redirect=True):
    '''reset_preview will delete the battery experiments for the preview user, meaning
    the preview can be restarted
    :param bid: the battery id
    :param redirect: if True, will redirect back to battery page, with message of reset
    (default is True, should only be false if called by server)
    '''
    preview_user = get_worker("DUMMY")
    battery = get_battery(bid,request)
    experiments = battery.experiment_set.all()
    preview_user.experiments_completed = preview_user.experiments_completed.exclude(id__in=[x.id for x in experiments])
    preview_user.save()
    if redirect == True:
        message = "Dummy worker history successfully reset."
        return view_battery(request,battery.id,message=message)
    

# Serving ----------------------------------------------------------------------
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


# Route the user to the next experiment
@csrf_exempt
def battery_router(request,bid,eid=None,userid=None,no_send=False):
    '''battery_router will direct the user (determined from the session variable) to an uncompleted experiment. If an
    experiment id is provided, the redirect is being sent from a completed experiment, and we log the experiment as completed
    first. 
    :param bid: the battery id
    :param eid: the experiment id, if provided, means we are submitting a result
    :param userid: the userid, will be "DUMMY" if doing a battery preview
    :param no_send: don't send result to email, default is False
    '''
    # No robots allowed!
    if request.user_agent.is_bot:
        return render_to_response("messages/robot_sorry.html")

    # Is this a valid user?
    preview = False
    if userid != "DUMMY": # not a preview battery
        userid = request.session.get('worker_id', None)
        if userid == None:
            return render_to_response("messages/invalid_id_sorry.html")
    else:
        # If no_send is defined, then don't send
        preview = True
        no_send = request.session.get('no_send', False)
    
    worker = get_worker(userid)

    # Retrieve the battery based on the bid
    battery = get_battery(bid,request)

    # If there is a post, we are finishing an experiment and sending data
    if request.method == "POST" and eid != None:

        experiment = get_experiment(eid,request)
   
        # If it's a survey, format the results before sending
        data = request.POST

        if experiment.template == "survey":
            data = complete_survey_result(experiment,data)
        
        else:
            data = dict(data)

        # Mark the experiment as completed    
        if experiment not in worker.experiments_completed.all():

            # Only send data if the user hasn't completed it yet
            if no_send != True:
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
        # If it's a preview, reset it before showing the final page
        if preview == True:
            reset_preview(request,bid,redirect=False)
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
