from django.contrib import admin

from .models import LocationReport, Employee


@admin.register(LocationReport)
class LocationReportAdmin(admin.ModelAdmin):
    list_display = ("id", "latitude", "longitude", "accuracy", "timestamp_ms", "recorded_at", "created_at")
    list_filter = ("created_at",)
    search_fields = ("latitude", "longitude")

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("id", "last_name", "first_name", "position", "created_at")
    list_filter = ("created_at",)
    search_fields = ("last_name", "first_name", "position")