
import ConfigParser
import datetime
import json
import os
import pandas
from requests import Session

from django.conf import settings

from expdj.apps.experiments.models import Experiment
from expdj.settings import BASE_DIR

# RESULTS UTILS
def to_dict(input_ordered_dict):
    '''to_dict converts an input ordered dict into a standard dict
    :param input_ordered_dict: the ordered dict
    '''
    return json.loads(json.dumps(input_ordered_dict))


def get_worker_experiments(worker,battery,completed=False):
    '''get_worker_experiments returns a list of experiment objects that
    a worker has/has not completed for a particular battery
    :param completed: boolean, default False to return uncompleted experiments
    '''
    battery_tags = Experiment.objects.filter(battery=battery)
    worker_completed = worker.experiments_completed.all()

    if completed==False: # uncompleted experiments
        return [e for e in battery_tags if e not in worker_completed]
    else: # completed experiments
        return [e for e in worker_completed if e in battery_tags]


def get_time_difference(d1,d2,format='%Y-%m-%d %H:%M:%S'):
    '''calculate difference between two time strings, t1 and t2, returns minutes'''
    if isinstance(d1,str):
        d1 = datetime.datetime.strptime(d1, format)
    if isinstance(d2,str):
        d2 = datetime.datetime.strptime(d2, format)
    return (d2 - d1).total_seconds() / 60
