from django.conf.urls import patterns, url
from django.views.generic.base import TemplateView
import expdj.apps.experiments.views as expv
from expdj import settings


urlpatterns = patterns('',

    # Experiments and Surveys
    url(r'^experiments$', expv.experiments_view, name="experiments"),
    url(r'^experiments/(?P<eid>.+?)/preview$',expv.preview_experiment,name='preview_experiment'),
    url(r'^surveys/(?P<bid>\d+|[A-Z]{8})/survey/add$',expv.new_survey,name='new_survey'),

    # Experiments in Batteries
    url(r'^experiments/(?P<bid>\d+|[A-Z]{8})/add$',expv.upload_experiment,name='upload_experiment'),
    url(r'^experiments/(?P<eid>\d+|[A-Z]{8})/$',expv.view_experiment,name='experiment_details'),
    url(r'^experiments/(?P<eid>\d+|[A-Z]{8})/export$',expv.download_experiment,name='download_experiment'),
    url(r'^experiments/(?P<bid>\d+|[A-Z]{8})/save$',expv.save_experiment,name='save_experiment'),
    url(r'^experiments/(?P<bid>\d+|[A-Z]{8})/(?P<eid>\d+|[A-Z]{8})/customize$',expv.edit_experiment,name='edit_experiment'),
    url(r'^experiments/(?P<bid>\d+|[A-Z]{8})/(?P<eid>\d+|[A-Z]{8})/order$',expv.change_experiment_order, name='change_experiment_order'),
    url(r'^experiments/(?P<bid>\d+|[A-Z]{8})/(?P<eid>\d+|[A-Z]{8})/remove$',expv.remove_experiment,name='remove_experiment'),

    # Router
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/(?P<eid>\d+|[A-Z]{8})/go$', expv.battery_router, name="battery_router"),
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/go$', expv.battery_router, name="battery_router"),

    # Batteries
    url(r'^batteries/$', expv.batteries_view, name="batteries"),
    url(r'^my-batteries/(?P<uid>\d+|[A-Z]{8})/$', expv.batteries_view, name="batteries"),
    url(r'^batteries/new$',expv.edit_battery,name='new_battery'),
    url(r'^batteries/add$',expv.add_battery,name='add_battery'),
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/edit$',expv.edit_battery,name='edit_battery'),
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/$',expv.view_battery, name='battery_details'),
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/delete$',expv.delete_battery,name='delete_battery'),

    # Preview options
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/(?P<no_send>\d+|[A-Z]{8})/preview$',expv.preview_battery,name='preview_battery'), # intro preview, don't send result
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/preview$',expv.preview_battery,name='preview_battery'), # intro preview, send result
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/preview/reset$',expv.reset_preview,name='reset_preview'), # intro preview, don't send result

    # Deployment Options
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/(?P<userid>\d+|[A-Za-z0-9-]{30,36})/serve$',expv.intro_battery,name='intro_battery'),
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/(?P<keyid>\d+|[A-Za-z0-9-]{32})/anon$',expv.serve_battery_anon,name='serve_battery_anon'),
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/serve/gmail$',expv.serve_battery_gmail,name='serve_battery_gmail'),
    url(r'^cookie/$',expv.enable_cookie_view,name='enable_cookie_view')
)

if settings.DEBUG:
    urlpatterns += patterns('',
        url(r'^static/(?P<path>.*)$', 'django.views.static.serve', {
            'document_root': settings.MEDIA_ROOT,
        }),
)
