from django.views.generic.base import TemplateView
from django.conf.urls import patterns, url
import expdj.apps.api.routes as routes

urlpatterns = patterns('',
    url(r'^routes/repos/view$',routes.view_repo,name='view_repo'),
    url(r'^api/battery$',routes.view_battery,name='api_batteries'),
    url(r'^api/battery/(?P<bid>\d+|[A-Z]{8})$',routes.view_battery,name='api_battery'), # specific battery, include experiments
    url(r'^api/experiment$',routes.view_experiment,name='api_experiments'),             # all experiments
    url(r'^api/experiment/(?P<eid>\d+|[A-Z]{8})$',routes.view_experiment,name='api_experiment'),
)
