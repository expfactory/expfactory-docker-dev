from expdj.apps.experiments.models import Experiment, Battery
from expdj.apps.api.utils import get_experiment_selection
from expdj.settings import (
   STATIC_ROOT,BASE_DIR,MEDIA_ROOT,MEDIA_URL,REPLY_TO, DOMAIN_NAME
)
from expfactory.experiment import get_experiments,load_experiment
from expfactory.survey import export_questions, generate_survey
from expfactory.utils import copy_directory

from django.db.models import Min
from django.template import Context, Template
from django.template.loader import get_template

from numpy.random import choice
from datetime import datetime
from git import Repo
from glob import glob

import json
import os
import pandas
import random
import re
import shutil
import tempfile

media_dir = os.path.join(BASE_DIR,MEDIA_ROOT)

EXPERIMENT_ROOT = "%s/experiments" %(media_dir)
if not os.path.exists(EXPERIMENT_ROOT):
    os.mkdir(EXPERIMENT_ROOT)


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
    install_dir = battery.get_install_dir()
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
            success = install_experiment_static(experiment=new_experiment,
                                                battery=battery,
                                                to_dir=output_folder,
                                                from_dir=experiment_folder,
                                                version="%s\n%s" %(repo_url,commit))
            if success == False:
                errored_experiments.append(experiment['exp_id'])
      
        except:
            errored_experiments.append(experiment['exp_id'])

    # Remove the temporary directory, return message
    shutil.rmtree(tmpdir)
    message = None
    if len(errored_experiments) > 0:
        message = "Experiments %s had error installing." %(",".join(errored_experiments))
    return message


def install_experiment_static(experiment,battery,to_dir,from_dir,update=True,version=None):
    '''install_experiment_static will install an experiment object static files to
    the battery static folder. In the case of a special expfactory template (survey, experiment,
    or game) the template is rendered and then saved. If successful, returns True, otherwise False.
    :param experiment: the expdj.apps.experiments.models.Experiment
    :param battery: the battery object, for use to get the battery name and route URL
    :param to_dir: the directory to install to, typically in a battery folder
    :param from_dir: the temporary directory
    :param remove_tmp: remove the temporary experiment folder when finished
    :param update: if the experiment files exist, remove them and install again (an update)
    :param version: if specified, will write a version id to the folder in file VERSION
    '''
    if os.path.exists(to_dir):
        if update == True:
            shutil.rmtree(to_dir)
        else:
            # Experiment static install fail, found files and update is not True
            return False    
    # Copy all experiment files into the folder
    copy_directory(from_dir,to_dir)
    # If the experiment template is special, we need to render the files
    if experiment.template == "survey":
        template = get_template("surveys/serve_battery.html")
        survey = load_experiment(to_dir)
        # Form action is to submit data to email database via formspree
        form_action = ("https://formspree.io/%s" %(battery.email)).encode('utf-8')
        runcode,validation = generate_survey(survey,to_dir,form_action=form_action,csrf_token=True)
        # We want to include hidden fields with experiment factory reply-to address, redirect, and subject
        router_url = "%s%s" %(DOMAIN_NAME,battery.get_router_url(experiment.id))
        hidden_fields = '<input type="text" name="_replyto" placeholder="%s"/>' %(REPLY_TO)
        hidden_fields = '%s<input type="hidden" name="_next" value="%s"/>' %(hidden_fields,router_url)
        hidden_fields = '<input type="hidden" name="_subject" value="[EXPFACTORY][RESULT][%s][%s][%s]"/>' %(hidden_fields,battery.name,experiment.name)
        
        runcode.replace("{% csrf_token %}",hidden_fields.encode('utf-8'))
        # static path should be replaced with web path
        url_path = "%s/" %(to_dir.replace(MEDIA_ROOT,MEDIA_URL[:-1])) 
        # prepare static files paths
        css,js = prepare_header_scripts(survey,url_prefix=url_path)
        context = Context({"validation":validation,
                           "run":runcode,
                           "css":css,
                           "js":js})
        index_html = template.render(context)
        index_file = "%s/index.html" %(to_dir)
        index_file = write_template(index_html,index_file)
    # If provided, write the version variable to the folder
    if version != None:
        write_template(version,"%s/VERSION" %(to_dir))
    return True

def write_template(html_snippet,output_file):
    '''write_template will write an html_snippet to an output_file
    :param html_snippet: the html to write to file
    :param output_file: the output file to write to
    '''
    filey = open(output_file,'w')
    filey.write(html_snippet.encode('utf-8'))
    filey.close()
    return output_file


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


def prepare_header_scripts(experiment,url_prefix="",join=True):
    '''prepare_header_scripts takes in a list of scripts from the run.js, and returns a list
    of formatted <script> and <link> objects.
    :param experiment: the loaded experiment object.
    :param url_prefix: an optional url_prefix to include before static files return string for js and css scripts to insert into a page based on battery path structure
    :param join: If true, will join each of the css and js lists
    '''
    js = ""
    css = ""

    if isinstance(experiment,list):
        experiment = experiment[0]

    scripts = experiment["run"]
    tag = experiment["exp_id"]

    for s in scripts:
        script = s.split("?")[0]
        ext = sniff_script_extension(script)

        # Do we have a relative experiment path?
        if len(script.split("/")) == 1:
            if ext == "js":
                js = "%s\n<script src='%s%s'></script>" %(js,url_prefix,s)
            elif ext == "css":
                css = "%s\n<link rel='stylesheet' type='text/css' href='%s%s'>" %(css,url_prefix,s)
        # Do we have an https/https path?
        elif re.search("^http",script):
            if ext == "js":
                js = "%s\n<script src='%s'></script>" %(js,s)
            elif ext == "css":
                css = "%s\n<link rel='stylesheet' type='text/css' href='%s'>" %(css,s)
 
    if join == True:
        return "".join(css),"".join(js)
    return css,js

def sniff_script_extension(s):
    '''sniff_script_extension will attempt to return if a script is css, or js based on its path.
    :param s: the script ath to sniff:
    '''
    script = s.split("?")[0]
    ext = script.split(".")[-1]
    # Do we have a relative experiment path?
    if ext == "js":
        return "js"
    elif ext == "css":
        return "css"        
    elif re.search("css",script):
        return "css"
    elif re.search("js",script):
        return "js"
    return "css"
