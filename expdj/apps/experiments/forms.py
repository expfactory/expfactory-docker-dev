from crispy_forms.layout import Layout, Div, Submit, HTML, Button, Row, Field, Hidden
from crispy_forms.bootstrap import AppendedText, PrependedText, FormActions, TabHolder, Tab
from expdj.apps.experiments.models import Experiment, Battery
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from django.forms import ModelForm
from django import forms
from glob import glob
import os
from expdj.settings import BASE_DIR

# Material Design Lite color choices
COLOR_CHOICES = (('amber', 'Amber',), 
                 ('blue', 'Blue',),
                 ('blue-grey','Blue Grey',),
                 ('brown', 'Brown',),
                 ('cyan', 'Cyan',),
                 ('deep-orange', 'Deep Orange',),
                 ('deep-purple', 'Deep Purple',),
                 ('green', 'Green',),
                 ('grey', 'Grey',),
                 ('indigo', 'Indigo',),
                 ('light-blue', 'Light Blue',),
                 ('light-green', 'Light Green',),
                 ('lime', 'Lime',),
                 ('orange', 'Orange',),
                 ('pink', 'Pink',),
                 ('purple', 'Purple',),
                 ('red', 'Red',),
                 ('teal', 'Teal',),
                 ('yellow', 'Yellow',))

class SurveyForm(forms.Form):
    '''make a new (static) survey, with fields corresponding to the data in the config.json.
    the questions are rendered dynamically into a table.
    '''
    # make the exp_id from this, give error to user if already exists
    name = forms.CharField(label='exp_id', max_length=250)
    base_color = forms.CharField(
        label='base_color',
        required=True,
        widget=forms.Select(choices=COLOR_CHOICES),
        help_text="The primary page color for selected buttons and headers."
    )
    accent_color = forms.CharField(
        label='accent_color',
        required=True,
        widget=forms.Select(choices=COLOR_CHOICES),
        help_text="The accent page color for buttons and other details."
    )
    # see colors at https://getmdl.io/customize/
    notes = forms.CharField(widget=forms.Textarea,
                            help_text="Any additional or important notes about the survey.")

    # This will need to be external required files, along with defaults
    #run = forms.FileField(help_text="Any additional files to keep with survey") # deactivating for now
    cognitive_atlas_task_id = forms.CharField(required=False,
                                              help_text="""A <a href='http://www.cognitiveatlas.org' target='_blank'>
                                                           cognitive atlas</a> task unique id (e.g., trm_*) to link to
                                                           additional meta-data about the assessment.""")
    contributors = forms.CharField(widget=forms.Textarea,help_text="Comma separated list of contributors.")
    time = forms.IntegerField(help_text="A recommended maximum time for the survey to be completed.")
    reference = forms.URLField(required=False,label='reference')
    publish = forms.BooleanField(help_text="Should the survey be active when published?")

    def clean(self):
        cleaned_data = super(SurveyForm, self).clean()
        return cleaned_data

    def __init__(self, *args, **kwargs):

        super(SurveyForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-8'
        self.helper.layout = Layout()
        tab_holder = TabHolder()
        self.helper.add_input(Submit("submit", "Save"))


class ExperimentForm(ModelForm):

    class Meta:
        model = Experiment
        fields = ("name","reference","order")

    def clean(self):
        cleaned_data = super(ExperimentForm, self).clean()
        return cleaned_data

    def __init__(self, *args, **kwargs):

        super(ExperimentForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-8'
        self.helper.layout = Layout()
        tab_holder = TabHolder()
        self.helper.add_input(Submit("submit", "Save"))


class BatteryForm(ModelForm):

    class Meta:
        model = Battery
        fields = ('name', 'email','sendgrid','active','description','consent','advertisement','instructions','maximum_time',
                  'presentation_order','required_batteries','restricted_batteries','private')

    def clean(self):
        cleaned_data = super(BatteryForm, self).clean()
        return cleaned_data

    def __init__(self, *args, **kwargs):

        super(BatteryForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-8'
        self.helper.layout = Layout()
        tab_holder = TabHolder()
        self.helper.add_input(Submit("submit", "Save"))
