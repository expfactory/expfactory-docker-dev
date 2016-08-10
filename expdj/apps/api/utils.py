from expdj.apps.experiments.models import Experiment
from expfactory.experiment import get_experiments
from expfactory.utils import copy_directory
from glob import glob
from git import Repo
import tempfile
import shutil
import random
import pandas
import json
import os
import re


def download_repo(repo_url,destination):
    '''download_repo
    Download a github repo to a "destination"
    :param repo_url: should be the URL for the repo.
    :param destination: the full path to the destination for the repo
    '''
    return Repo.clone_from(repo_url, destination)


def download_repos(repos,tmpdir=None):
    '''download_repos
    Download some github repo with experiments to a temporary folder to build a custom battery, return the path to the tmp folder
    :param tmpdir: The directory to download to. If none, a temporary directory will be made
    :param repos: A list of repositories to download
    '''
    if not isinstance(repos,list):
        repos = [repos]
    if not tmpdir:
        tmpdir = tempfile.mkdtemp()
    for r in range(len(repos)):
        repo = repos[r]
        # Will need to catch any errors here
        download_repo(repo,"%s/%s/" %(tmpdir,r))
    return tmpdir


def get_experiment_selection(repo_urls,tmpdir=None,remove_tmp=True):
    '''get_experiment_selection will return a list of valid experiments from a github repo
    :param repo_urls: a list of github repo urls
    :param tmpdir: provide a custom temporary directory, will be generated if not provided
    :param remove_tmp: delete the temporary directory at finish (default True)
    '''
    tmpdir = download_repos(repo_urls,tmpdir=tmpdir)
    # Get all experiments in subfolders
    subfolders = glob("%s/*" %tmpdir)
    experiments = []
    for subfolder in subfolders:
        new_experiments = get_experiments(subfolder,load=True,warning=False)    
        experiments = experiments + new_experiments
    experiments = [x[0] for x in experiments]
    if remove_tmp == True:
        shutil.rmtree(tmpdir)
    return experiments
