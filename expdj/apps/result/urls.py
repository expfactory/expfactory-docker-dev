from expdj.apps.result.views import *
from expdj.apps.experiments.views import sync
from django.views.generic.base import TemplateView
from django.conf.urls import patterns, url
from django.views.generic.base import TemplateView
from expdj.apps.experiments.views import sync

urlpatterns = patterns('',
    url(r'^sync/(?P<rid>\d+|[A-Z]{8})/$',sync,name='sync_data'),
    url(r'^sync/$',sync,name='sync_data'),
    url(r'^finished$', finished_view, name="finished_view"),
)
