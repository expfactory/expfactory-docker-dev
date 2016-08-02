from django.contrib.sitemaps import Sitemap
from expdj.apps.experiments.utils import get_experiment_type
from expdj.apps.experiments.models import Experiment

class BaseSitemap(Sitemap):
    priority = 0.5

    #def lastmod(self, obj):
    #    return obj.modify_date

    def location(self,obj):
        return obj.get_absolute_url()


class ExperimentSitemap(BaseSitemap):
    changefreq = "weekly"
    def items(self):
        return [x for x in Experiment.objects.all() if get_experiment_type(x) == "experiments"]

class SurveySitemap(BaseSitemap):
    changefreq = "weekly"
    def items(self):
        return [x for x in Experiment.objects.all() if get_experiment_type(x) == "surveys"]

class GameSitemap(BaseSitemap):
    changefreq = "weekly"
    def items(self):
        return [x for x in Experiment.objects.all() if get_experiment_type(x) == "games"]
