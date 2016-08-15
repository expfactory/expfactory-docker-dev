from __future__ import absolute_import

import numpy
import os
from sendgrid.helpers.mail import *
from sendgrid import *

from celery import shared_task, Celery

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from expdj.apps.experiments.models import Experiment, Battery
from expdj.apps.experiments.utils import get_experiment_type
from expdj.apps.result.models import get_worker
from expdj.apps.result.utils import generate_email
from expdj.settings import REPLY_TO, DOMAIN_NAME


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expdj.settings')
app = Celery('expdj')
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

@shared_task
def send_result(eid,wid,data):
    '''send_result will use the sendgrid email API to send a result object to a worker. If there
    is an error, the user will be emailed instead using expfactory email, and the battery status
    will be made inactive.
    :param eid: the experiment id
    :param data: the data object (json)
    '''
    try:
        # Retrieve worker, experiment, and battery
        worker = get_worker(wid)
        experiment = Experiment.objects.get(id=eid)
        battery = experiment.battery

        # Generate email and send with sendgrid
        email = generate_email(battery,experiment,worker,data)
        sg = SendGridAPIClient(apikey=battery.sendgrid)
        response = sg.client.mail.send.post(request_body=email)
        if response.status_code != 202:
            failed_send(battery,experiment,worker)
    except:
        failed_send(battery,experiment,worker)


def failed_send(battery,experiment,worker):
    '''If the battery fails to send, we send the user the information and disable the battery.
    The site admin is also notified.
    '''
    # Deactivate the battery
    battery.active = False
    battery.save()

    # Notify the user
    subject = "[EXPFACTORY][ERROR] The Experiment Factory Email Sending Error"
    body = """Hello!\n\n Your recent attempt to send an Experiment Factory result email 
              using the SendGrid API was not successful for participant with id %s and 
              experiment %s. To prevent loss of future data, we have temporarily 
              deactivated your battery. Please check your SendGrid account quota and API 
              Key at app.sendgrid.com, and then re-activate your battery at %s\%s. 
              Please reach out to us if you have any questions!\n\nBest,\n\n
              The Experiment Factory Team.""" %(worker.id,experiment.name,DOMAIN_NAME,battery.get_absolute_url())
    to_email = [battery.owner.email,battery.email]
    message = EmailMessage(subject=subject,
                           body=body,
                           from_email=REPLY_TO,
                           to=to_email)
    message.send()


def check_battery_dependencies(current_battery, worker):
    '''
    check_battery_dependencies looks up all of a workers completed 
    experiments and places them in a dictionary 

    organized by battery_id. Each of these buckets of results is
    iterated through to check that every experiment in that battery has
    been completed. In this way a list of batteries that a worker has 
    completed is built. This list is then compared to the lists of 
    required and restricted batteries to determine if the worker is 
    eligible to attempt the current battery.
    '''
    worker_completed = worker.experiments_completed.all()
    
    worker_result_batteries = {}
    for completed in worker_completed:
        if worker_result_batteries.get(completed.battery.id):
            worker_result_batteries[completed.battery.id].append(completed)
        else:
            worker_result_batteries[completed.battery.id] = []
            worker_result_batteries[completed.battery.id].append(completed)

    worker_completed_batteries = []
    for battery_id in worker_result_batteries:
        completed = worker_result_batteries[battery_id]
        all_experiments_complete = True
        result_experiment_list = [x.id for x in completed]
        battery_experiments = Experiment.objects.filter(battery=current_battery)
        for experiment in battery_experiments:
            if experiment.id not in result_experiment_list:
                all_experiments_complete = False
                break
        if all_experiments_complete:
            worker_completed_batteries.append(battery_id)
            continue

    missing_batteries = []
    for required_battery in current_battery.required_batteries.all():
        if required_battery.id not in worker_completed_batteries:
            missing_batteries.append(required_battery)

    blocking_batteries = []
    for restricted_battery in current_battery.restricted_batteries.all():
        if restricted_battery.id in worker_completed_batteries:
            blocking_batteries.append(restricted_battery)

    return missing_batteries, blocking_batteries
