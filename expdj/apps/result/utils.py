from expdj.apps.experiments.models import Experiment
import ConfigParser
import datetime
import pandas
import json
import os

from django.conf import settings

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
    from expdj.apps.result.models import Result
    battery_tags = [x.template.exp_id for x in battery.experiments.all()]
    worker_experiments = Result.objects.filter(worker=worker,battery=battery)
    worker_tags = [x.experiment.exp_id for x in worker_experiments if x.completed==True]

    if completed==False:
        experiment_selection = [e for e in battery_tags if e not in worker_tags]
    else:
        experiment_selection = [e for e in worker_tags if e in battery_tags]
    return Experiment.objects.filter(template__exp_id__in=experiment_selection,
                                     battery_experiments__id=battery.id)


def get_time_difference(d1,d2,format='%Y-%m-%d %H:%M:%S'):
    '''calculate difference between two time strings, t1 and t2, returns minutes'''
    if isinstance(d1,str):
        d1 = datetime.datetime.strptime(d1, format)
    if isinstance(d2,str):
        d2 = datetime.datetime.strptime(d2, format)
    return (d2 - d1).total_seconds() / 60
