import expdj.apps.result.views as rviews
from django.views.generic.base import TemplateView
from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^finished$', rviews.finished_view, name="finished_view"),
    url(r'^sync$', rviews.sync, name="sync"), #dummy view for expfactory.js
)
