from django.contrib.sitemaps import Sitemap
from expdj.apps.experiments.utils import get_experiment_type
from expdj.apps.experiments.models import Experiment, Battery

class BaseSitemap(Sitemap):
    priority = 0.5
    def location(self,obj):
        return obj.get_absolute_url()

class ExperimentSitemap(BaseSitemap):
    changefreq = "weekly"
    def items(self):
        return [x for x in Experiment.objects.filter(battery__private=False) if get_experiment_type(x) == "experiments"]

class SurveySitemap(BaseSitemap):
    changefreq = "weekly"
    def items(self):
        return [x for x in Experiment.objects.filter(battery__private=False) if get_experiment_type(x) == "surveys"]

class GameSitemap(BaseSitemap):
    changefreq = "weekly"
    def items(self):
        return [x for x in Experiment.objects.filter(battery__private=False) if get_experiment_type(x) == "games"]

class CustomSitemap(BaseSitemap):
    changefreq = "weekly"
    def items(self):
        return [x for x in Experiment.objects.filter(battery__private=False) if get_experiment_type(x) == "custom"]

class BatterySitemap(BaseSitemap):
    changefreq = "weekly"

    def items(self):
        return Battery.objects.filter(private=False)

    def location(self,obj):
        return obj.get_absolute_url()

