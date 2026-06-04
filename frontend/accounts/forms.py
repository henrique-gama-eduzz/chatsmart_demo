from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import UserProfile, DatabaseConnection

class SignUpForm(UserCreationForm):
    email = forms.EmailField(max_length=254, required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Digite seu endereço de email'
    }))
    
    # Override the init method to set form-control class on all fields
    def __init__(self, *args, **kwargs):
        super(SignUpForm, self).__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Nome de usuário'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Senha'
    }))

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('organization', 'role', 'bio')
        widgets = {
            'organization': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class DatabaseConnectionForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False)
    
    class Meta:
        model = DatabaseConnection
        fields = ['name', 'database_type', 'host', 'port', 'database_name', 
                  'username', 'password', 'connection_string', 'ssl_enabled']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'database_type': forms.Select(attrs={'class': 'form-select'}),
            'host': forms.TextInput(attrs={'class': 'form-control'}),
            'port': forms.TextInput(attrs={'class': 'form-control'}),
            'database_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'connection_string': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'ssl_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        database_type = cleaned_data.get('database_type')
        connection_string = cleaned_data.get('connection_string')
        
        # If using SQLite, only database_name is required
        if database_type == 'sqlite':
            if not cleaned_data.get('database_name'):
                self.add_error('database_name', 'Database name is required for SQLite')
        # For other databases, check if either connection string or required fields are provided
        elif not connection_string:
            if not cleaned_data.get('host') and database_type != 'sqlite':
                self.add_error('host', 'Host is required unless connection string is provided')
            if not cleaned_data.get('database_name'):
                self.add_error('database_name', 'Database name is required')
        
        return cleaned_data
