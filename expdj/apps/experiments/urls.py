from django.conf.urls import patterns, url
from django.views.generic.base import TemplateView
import expdj.apps.experiments.views as expv
from expdj import settings


urlpatterns = patterns('',

    # Experiments
    url(r'^experiments$', expv.experiments_view, name="experiments"),
    url(r'^experiments/(?P<eid>.+?)/preview$',expv.preview_experiment,name='preview_experiment'),

    # Experiments in Batteries
    url(r'^experiments/(?P<bid>\d+|[A-Z]{8})/add$',expv.add_experiment,name='add_experiment'),
    url(r'^experiments/(?P<bid>\d+|[A-Z]{8})/save$',expv.save_experiment,name='save_experiment'),
    url(r'^experiments/(?P<bid>\d+|[A-Z]{8})/(?P<eid>\d+|[A-Z]{8})/customize$',expv.edit_experiment,name='edit_experiment'),
    url(r'^experiments/(?P<bid>\d+|[A-Z]{8})/(?P<eid>\d+|[A-Z]{8})/view$',expv.view_experiment, name='experiment_details'),
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
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/user$',expv.generate_battery_user,name='generate_battery_user'),
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/$',expv.view_battery, name='battery_details'),
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/delete$',expv.delete_battery,name='delete_battery'),

    # Deployment Options
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/preview$',expv.preview_battery,name='preview_battery'), # intro preview without subid
    url(r'^batteries/(?P<bid>\d+|[A-Z]{8})/dummy$',expv.dummy_battery,name='dummy_battery'),       # running without subid
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
