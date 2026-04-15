from django import forms
from django.utils import timezone

from .models import Employee, Position, Zone


class ZoneForm(forms.ModelForm):
    polygon = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = Zone
        fields = ["name", "polygon"]

    def clean_polygon(self):
        value = self.cleaned_data["polygon"]
        if not value:
            raise forms.ValidationError("Нужно нарисовать полигон.")
        return value


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ["name"]


class ReportForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.none())
    zone = forms.ModelChoiceField(queryset=Zone.objects.none())
    start_datetime = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    end_datetime = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.all()
        self.fields["zone"].queryset = Zone.objects.all()
        if not self.is_bound:
            now_local = timezone.localtime(timezone.now())
            start_default = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            end_default = now_local.replace(hour=23, minute=59, second=0, microsecond=0)
            self.fields["start_datetime"].initial = start_default
            self.fields["end_datetime"].initial = end_default
