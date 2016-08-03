from django.views.generic.base import TemplateView
from django.conf.urls import patterns, url
from expdj.apps.api.routes import view_repo

urlpatterns = patterns('',
    url(r'^routes/repos/view$',view_repo,name='view_repo'),
)
