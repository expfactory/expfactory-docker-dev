from expdj.apps.experiments.models import Battery, Experiment
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from expdj.apps.experiments import urls as experiment_urls
from django.contrib.auth.decorators import login_required
from rest_framework import routers, serializers, viewsets
from django.contrib.sitemaps.views import sitemap, index
from django.conf.urls import include, url, patterns
from expdj.apps.result.models import Worker
from expdj.apps.users import urls as users_urls
from django.http import Http404, HttpResponse
from expdj.apps.main import urls as main_urls
from expdj.apps.result import urls as result_urls
from expdj.apps.api import urls as api_urls
from django.conf.urls.static import static
from expdj.apps.result.utils import to_dict
from django.conf import settings
from django.contrib import admin
import os

# Custom error views
from django.conf.urls import ( handler404, handler500 )

# Sitemaps
from expdj.apps.api.sitemap import ExperimentSitemap, SurveySitemap, GameSitemap
sitemaps = {"experiments":ExperimentSitemap,
            "surveys":SurveySitemap,
            "games":GameSitemap}

# Configure custom error pages
handler404 = 'expdj.apps.main.views.handler404'
handler500 = 'expdj.apps.main.views.handler500'

# Seriailizers define the API representation
class BatterySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Battery
        fields = ('name', 'description')

class ExperimentSerializer(serializers.HyperlinkedModelSerializer):
    battery = BatterySerializer()
    class Meta:
        model = Experiment
        fields = ('exp_id','name','reference','version','template','battery')

class WorkerSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Worker
        fields = ["id"]

# ViewSets define the view behavior.
class ExperimentViewSet(viewsets.ModelViewSet):
    queryset = Experiment.objects.all()
    serializer_class = ExperimentSerializer

# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r'api/results', ExperimentViewSet)

admin.autodiscover()

urlpatterns = [ url(r'^', include(main_urls)),
                url(r'^', include(result_urls)),
                url(r'^', include(experiment_urls)),
                url(r'^accounts/', include(users_urls)),
                url(r'^', include(router.urls)),
                url(r'^', include(api_urls)),
#                url(r'^sitemap\.xml$', index, {'sitemaps': sitemaps}),
#                url(r'^sitemap-(?P<section>.+)\.xml$', sitemap, {'sitemaps': sitemaps}),
                url(r'^api/', include('rest_framework.urls', namespace='rest_framework')),
                url(r'^admin/', include(admin.site.urls))
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if settings.DEBUG:
    urlpatterns += patterns(
        '',
        url(r'^(?P<path>favicon\.ico)$', 'django.views.static.serve', {
            'document_root': settings.STATIC_ROOT}),
    )
