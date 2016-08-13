from __future__ import absolute_import

import numpy
import os

from celery import shared_task, Celery

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from expdj.apps.experiments.models import Experiment, Battery
from expdj.apps.experiments.utils import get_experiment_type
from expdj.apps.result.models import get_worker

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expdj.settings')
app = Celery('expdj')
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

@shared_task
def send_result(result):
    subject = "[expfactory][result]5"
    body = "This is an expriment factory result"
    from_email = "noreply@expfactory.org"
    to_email = ["vsochat@gmail.com"]
    message = EmailMessage(subject=subject,
                           body=body,
                           from_email=from_email,
                           to=to_email,
                           headers={'result-id': '12'})
    message.attach("attachment.json", '{"hello":"hello"}', "application/json")
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
        battery_experiments = Experiment.objects.filter(battery=battery)
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
