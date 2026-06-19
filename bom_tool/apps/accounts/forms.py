from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from .models import UserProfile


class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control bom-input',
            'placeholder': 'Username or Email',
            'autocomplete': 'username',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control bom-input',
            'placeholder': 'Password',
            'autocomplete': 'current-password',
        })
    )


class RegisterForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control bom-input', 'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control bom-input', 'placeholder': 'Last Name'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control bom-input', 'placeholder': 'Work Email'}))
    password = forms.CharField(min_length=8, widget=forms.PasswordInput(attrs={'class': 'form-control bom-input', 'placeholder': 'Password (min. 8 chars)'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control bom-input', 'placeholder': 'Confirm Password'}))
    company = forms.CharField(max_length=150, required=False,widget=forms.TextInput(attrs={'class': 'form-control bom-input', 'placeholder': 'Company (optional)'}))
    agree_terms = forms.BooleanField(required=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data['email']
        user.username = email  # Use email as username
        user.email = email
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            if self.cleaned_data.get('company'):
                user.profile.company = self.cleaned_data['company']
                user.profile.save()
        return user


class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control bom-input'}))
    last_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control bom-input'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control bom-input'}))

    class Meta:
        model = UserProfile
        fields = ['company', 'job_title', 'phone', 'bio', 'default_key_column', 'email_notifications', 'avatar']
        widgets = {
            'company': forms.TextInput(attrs={'class': 'form-control bom-input'}),
            'job_title': forms.TextInput(attrs={'class': 'form-control bom-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-control bom-input'}),
            'bio': forms.Textarea(attrs={'class': 'form-control bom-input', 'rows': 3}),
            'default_key_column': forms.TextInput(attrs={'class': 'form-control bom-input', 'placeholder': 'e.g., part_number'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control bom-input'}),
        }