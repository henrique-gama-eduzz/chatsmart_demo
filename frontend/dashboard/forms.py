from django import forms
from .models import Dataset, Analysis, Project

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class DatasetUploadForm(forms.ModelForm):
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        empty_label="Selecione um projeto",
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )
    
    class Meta:
        model = Dataset
        fields = ['project', 'file']
        widgets = {
            'file': forms.FileInput(attrs={'accept': '.csv,.xlsx', 'class': 'form-control'})
        }
    
    def __init__(self, user=None, *args, **kwargs):
        super(DatasetUploadForm, self).__init__(*args, **kwargs)
        if user:
            self.fields['project'].queryset = Project.objects.filter(owner=user)

class VariableSelectionForm(forms.Form):
    dependent_vars = forms.MultipleChoiceField(
        choices=[],
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=True,
        help_text="Quais resultados você está tentando melhorar? (ex: defeitos, tempo de ciclo)"
    )
    
    independent_vars = forms.MultipleChoiceField(
        choices=[],
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=True,
        help_text="Quais fatores podem afetar seus resultados? (ex: temperatura, operador)"
    )
    
    analysis_objective = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        required=True,
        help_text="Explique claramente o que você deseja descobrir ou melhorar com esta análise."
    )
    
    def __init__(self, columns=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if columns:
            column_choices = [(col, col) for col in columns]
            self.fields['dependent_vars'].choices = column_choices
            self.fields['independent_vars'].choices = column_choices

class ColumnDescriptionForm(forms.Form):
    def __init__(self, columns=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if columns:
            for column in columns:
                self.fields[f'desc_{column}'] = forms.CharField(
                    label=f"Descrição para '{column}'",
                    required=False,
                    widget=forms.TextInput(attrs={'class': 'form-control'})
                )

class AnalysisEditForm(forms.ModelForm):
    class Meta:
        model = Analysis
        fields = ['name', 'content']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'rows': 8, 'class': 'form-control'})
        }

class ExecuteAnalysisForm(forms.Form):
    analysis_id = forms.IntegerField(widget=forms.HiddenInput())
