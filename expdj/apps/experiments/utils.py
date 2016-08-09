from expdj.apps.experiments.models import Experiment
from expdj.apps.api.utils import get_experiment_selection
from expdj.settings import STATIC_ROOT,BASE_DIR,MEDIA_ROOT
from expfactory.vm import custom_battery_download
from expfactory.experiment import get_experiments
from expfactory.survey import export_questions
from expfactory.utils import copy_directory
from django.db.models import Min
from numpy.random import choice
from datetime import datetime
from glob import glob
from git import Repo
import tempfile
import shutil
import random
import pandas
import json
import os
import re

media_dir = os.path.join(BASE_DIR,MEDIA_ROOT)

# EXPERIMENT FACTORY PYTHON FUNCTIONS #####################################################

def get_experiment_type(experiment):
    '''get_experiment_type returns the installation folder (eg, games, surveys, experiments) based on the template specified in the config.json
    :param experiment: the ExperimentTemplate object
    '''
    if experiment.template in ["jspsych"]:
        return "experiments"
    elif experiment.template in ["survey"]:
        return "surveys"
    elif experiment.template in ["phaser"]:
        return "games"


def parse_experiment_variable(variable):
    experiment_variable = None
    if isinstance(variable,dict):
        try:
            description = variable["description"] if "description" in variable.keys() else None
            if "name" in variable.keys():
                name = variable["name"]
                if "datatype" in variable.keys():
                    if variable["datatype"].lower() == "numeric":
                        variable_min = variable["range"][0] if "range" in variable.keys() else None
                        variable_max = variable["range"][1] if "range" in variable.keys() else None
                        experiment_variable,_ = ExperimentNumericVariable.objects.update_or_create(name=name,
                                                                                                   description=description,
                                                                                                   variable_min=variable_min,
                                                                                                   variable_max=variable_max)
                    elif variable["datatype"].lower() == "string":
                        experiment_variable,_ = ExperimentStringVariable.objects.update_or_create(name=name,
                                                                                                  description=description,
                                                                                                  variable_options=variable_options)
                    elif variable["datatype"].lower() == "boolean":
                        experiment_variable,_ = ExperimentBooleanVariable.objects.update_or_create(name=name,description=description)
                    experiment_variable.save()
        except:
            pass
    return experiment_variable


def install_experiments(battery,repo_url,experiment_ids):
    '''install_experiments takes a list of exp_ids and a repo_url, and installs them to a particular battery_id. If the experiment already
    exists, it is completely overwritten.
    :param battery: the battery to install to, an expdj.apps.experiments.models.Battery
    :param repo_url: the Github URL of the experiment
    :param experiment_ids: a list of experiment (exp_ids) expected to be found in the config.json
    '''
    # Get the experiment selection, and install the experiment for the user
    tmpdir = tempfile.mkdtemp()
    experiment_selection = get_experiment_selection(repo_url,tmpdir=tmpdir,remove_tmp=False)
            
    # The git commit is saved with the experiment as the "version"
    repo_folder = "%s/0" %(tmpdir)
    repo = Repo(repo_folder)
    commit = repo.commit('master').__str__()

    # The function creates a folder for each repo, since we provided 1, the address is in 0
    experiment_selection = [x for x in experiment_selection if x['exp_id'] in experiment_ids] 
    experiment_folders = ["%s/%s" %(repo_folder,exp_id) for exp_id in experiment_ids]
    existing_folders = glob("%s/*" %repo_folder)
    experiment_folders = [x for x in experiment_folders if x in existing_folders]

    # For each experiment folder, create an experiment object, and save files to user static
    install_dir = "%s/experiments/%s" %(media_dir,battery.id)
    if not os.path.exists(install_dir):
        os.mkdir(install_dir)

    # We will save a list of errored_experiments
    errored_experiments = []
    
    for experiment in experiment_selection:
        try:
            experiment_folder = "%s/%s" %(repo_folder,experiment['exp_id'])

            # In case reference is a list, just take first
            if isinstance(experiment["reference"],list):
                reference = experiment["reference"][0]
            else:
                reference = experiment["reference"]

            # Create the experiment to add to the battery
            new_experiment,_ = Experiment.objects.update_or_create(exp_id=experiment["exp_id"],battery=battery,
                                                                   defaults={"name":experiment["name"],
                                                                             "time":experiment["time"],
                                                                             "reference":reference,
                                                                             "version":commit,
                                                                             "template":experiment["template"]})
            new_experiment.save()
                
            # Finally, install the experiment to its folder in the user's battery directory
            output_folder = "%s/%s" %(install_dir,experiment["exp_id"])
            if os.path.exists(output_folder):
                shutil.rmtree(output_folder)
            copy_directory(experiment_folder,output_folder)
                  
        except:
            errored_experiments.append(experiment['exp_id'])

    # Remove the temporary directory, return message
    shutil.rmtree(tmpdir)
    message = None
    if len(errored_experiments) > 0:
        message = "Experiments %s had error installing." %(",".join(errored_experiments))
    return message


# EXPERIMENT SELECTION #####################################################################

def select_random_n(experiments,N):
    '''select_experiments_N
    a selection algorithm that selects a random N experiments from list
    :param experiments: list of experiment.Experiment objects, with time variable specified in minutes
    :param N: the number of experiments to select
    '''
    if N>len(experiments):
        N=len(experiments)
    return choice(experiments,N).tolist()


def select_ordered(experiments,selection_number=1):
    '''select_ordered will return a list of the next "selection_number"
    of experiments. Lower numbers are returned first, and if multiple numbers
    are specified for orders, these will be selected from randomly.
    :param experiments: the list of Experiment objects to select from
    :param selection_number: the number of experiments to choose (default 1)
    '''
    next_value = experiments.aggregate(Min('order'))["order__min"]
    experiment_choices = [e for e in experiments if e.order == next_value]
    return select_random_n(experiment_choices,selection_number)


def select_experiments(battery,uncompleted_experiments,selection_number=1):
    '''select_experiments selects experiments based on the presentation_order variable
    defined in the battery (random or specific)
    :param battery: the battery object
    :param uncompleted_experiments: a list of Experiment objects to select from
    :param selection_number: the number of experiments to select
    '''
    if battery.presentation_order == "random":
        task_list = select_random_n(uncompleted_experiments,selection_number)
    elif battery.presentation_order == "specified":
        task_list = select_ordered(uncompleted_experiments,selection_number=selection_number)
    return task_list


def select_experiments_time(maximum_time_allowed,experiments):
    '''select_experiments_time
    a selection algorithm that selects experiments from list based on not exceeding some max time
    this function is not implemented anywhere, as the battery length is determined by experiments
    added to battery.
    :param maximum_time_allowed: the maximum time allowed, in seconds
    :param experiments: list of experiment.Experiment objects, with time variable specified in minutes
    '''
    # Add tasks with random selection until we reach the time limit
    task_list = []
    total_time = 0
    exps = experiments[:]
    while (total_time < maximum_time_allowed) and len(exps)>0:
        # Randomly select an experiment
        experiment = exps.pop(choice(range(len(exps))))
        if (total_time + experiment.template.time*60.0) <= maximum_time_allowed:
            task_list.append(experiment)
    return task_list

# GENERAL UTILS ############################################################################

def remove_keys(dictionary, keys):
    '''remove_key deletes a key from a dictionary'''
    if isinstance(keys,str):
        keys = [keys]
    new_dict = dict(dictionary) # in case Query dict
    for key in keys:
        if key in new_dict:
            del new_dict[key]
    return new_dict

def complete_survey_result(exp_id,taskdata):
    '''complete_survey_result parses the form names (question ids) and matches to a lookup table generated by expfactory-python survey module that has complete question / option information.
    :param experiment: the survey unique id, expected to be
    :param taskdata: the taskdata from the server, typically an ordered dict
    '''
    taskdata = dict(taskdata)
    experiment = [{"exp_id":exp_id}]
    experiment_folder = "%s/%s/%s" %(media_dir,"surveys",exp_id)
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
