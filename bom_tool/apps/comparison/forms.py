from django import forms
from .models import ComparisonSession


class ComparisonSessionForm(forms.ModelForm):
    master_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control bom-input d-none',
            'id': 'masterFileInput',
            'accept': '.csv,.xlsx,.xls,.json',
        }),
        label='Master BOM File',
        help_text='Upload your reference/master BOM file (CSV, XLSX, XLS, JSON).',
    )

    key_column = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control bom-input',
            'placeholder': 'e.g. part_number  (leave blank to auto-detect)',
        }),
        label='Key Column (optional)',
        help_text='Column used to match rows between files. Auto-detected if left blank.',
    )

    class Meta:
        model = ComparisonSession
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control bom-input',
                'placeholder': 'e.g. Q2-2024 PCB BOM Review',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control bom-input',
                'rows': 2,
                'placeholder': 'Optional notes about this comparison run…',
            }),
        }

    def clean_master_file(self):
        f = self.cleaned_data.get('master_file')
        if f:
            ext = '.' + f.name.rsplit('.', 1)[-1].lower()
            if ext not in ['.csv', '.xlsx', '.xls', '.json']:
                raise forms.ValidationError(f'Unsupported format "{ext}". Use CSV, XLSX, XLS, or JSON.')
            if f.size > 25 * 1024 * 1024:
                raise forms.ValidationError('File exceeds 25 MB limit.')
        return f