from django.urls import path

from .views import create_employee, ingest_location, list_positions, update_employee

urlpatterns = [
    path("employees/", create_employee, name="create_employee"),
    path("employees/<int:employee_id>/", update_employee, name="update_employee"),
    path("positions/", list_positions, name="list_positions"),
    path("locations/", ingest_location, name="ingest_location"),
]
