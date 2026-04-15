from django.urls import path

from .views import (
    DashboardLoginView,
    DashboardLogoutView,
    dashboard_home,
    position_create,
    position_delete,
    position_edit,
    position_list,
    report_view,
    zone_create,
    zone_edit,
    zone_list,
)

urlpatterns = [
    path("login/", DashboardLoginView.as_view(), name="dashboard_login"),
    path("logout/", DashboardLogoutView.as_view(), name="dashboard_logout"),
    path("", dashboard_home, name="dashboard_home"),
    path("zones/", zone_list, name="dashboard_zones"),
    path("zones/new/", zone_create, name="dashboard_zone_create"),
    path("zones/<int:zone_id>/", zone_edit, name="dashboard_zone_edit"),
    path("positions/", position_list, name="dashboard_positions"),
    path("positions/new/", position_create, name="dashboard_position_create"),
    path("positions/<int:position_id>/", position_edit, name="dashboard_position_edit"),
    path("positions/<int:position_id>/delete/", position_delete, name="dashboard_position_delete"),
    path("report/", report_view, name="dashboard_report"),
]
