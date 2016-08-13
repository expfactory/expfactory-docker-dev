#!/bin/bash
python manage.py makemigrations result
python manage.py makemigrations experiments
python manage.py makemigrations main
python manage.py migrate
python manage.py migrate auth
python manage.py collectstatic --noinput
uwsgi uwsgi.ini
