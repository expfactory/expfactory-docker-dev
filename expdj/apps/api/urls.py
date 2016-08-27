from django.views.generic.base import TemplateView
from django.conf.urls import patterns, url
import expdj.apps.api.routes as routes

urlpatterns = patterns('',
    url(r'^routes/repos/view$',routes.view_repo,name='view_repo'),
    url(r'^api/battery$',routes.view_battery,name='view_battery'),
    url(r'^api/battery/(?P<bid>\d+|[A-Z]{8})$',routes.view_battery,name='view_battery'), # specific battery, include experiments
)
