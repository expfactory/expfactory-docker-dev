import ConfigParser
import datetime
import json
import os
import pandas

from django.conf import settings

from expdj.apps.experiments.models import Experiment
from expdj.settings import BASE_DIR, REPLY_TO, REPLY_TO_NAME

from expfactory.survey import export_questions

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


def generate_email(battery,experiment,worker,data):
    '''send_result will use sendgrid API to send a result object to a user as an email attachment.
    :param battery: The expdj.apps.experiment.Battery
    :param data: the data result (json) to send
    '''
    if not isinstance(data,dict):
        data = {"result":data}
    data = json.dumps(to_dict(data))
   
    to_email = battery.email
    subject = "[EXPFACTORY][RESULT][%s][%s]" %(battery.name,experiment.name)
    body = "Experiment Factory Result Data\n%s\n%s\n%s" %(battery.flat(),
                                                          experiment.flat(),
                                                          worker.flat())
    filename = "%s_%s_%s.json" %(experiment.exp_id,experiment.id,worker.id)

    return  {"personalizations": [{"to": [{"email": to_email}],
             "subject": subject}],
             'attachments': [{'content': data,'type': 'application/json','filename': filename}],
             "from": {"email": REPLY_TO},
             "content": [{"type": "text/plain","value": body}]}


def complete_survey_result(experiment,taskdata):
    '''complete_survey_result parses the form names (question ids) and matches to a lookup table generated by expfactory-python survey module that has complete question / option information.
    :param experiment: the experiment object
    :param taskdata: the taskdata from the server, typically an ordered dict
    '''
    taskdata = dict(taskdata)
    experiment_folder = experiment.get_install_dir()
    experiment = [{"exp_id":experiment.exp_id}]
    question_lookup = export_questions(experiment,experiment_folder)
    final_data = {}
    for queskey,quesval in taskdata.iteritems():
        if queskey in question_lookup:
           complete_question = question_lookup[queskey]
           complete_question["response"] = quesval[0]
        else:
           complete_question = {"response":quesval[0]}
        final_data[queskey] = complete_question
    return final_data
