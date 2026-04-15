import json

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .forms import PositionForm, ReportForm, ZoneForm
from .models import Employee, LocationReport, Position, Zone
from .services import build_zone_report, load_route_segments


def _parse_float(value, field_name):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {field_name}")


def _parse_int(value, field_name):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {field_name}")


@csrf_exempt
def ingest_location(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST is allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    try:
        latitude = _parse_float(payload.get("latitude"), "latitude")
        longitude = _parse_float(payload.get("longitude"), "longitude")
        accuracy = payload.get("accuracy")
        accuracy = _parse_float(accuracy, "accuracy") if accuracy is not None else None
        timestamp_ms = _parse_int(payload.get("timestamp"), "timestamp")
        employee_id = _parse_int(payload.get("employee_id"), "employee_id")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        employee = Employee.objects.get(id=employee_id)
    except Employee.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    recorded_at = timezone.datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

    report = LocationReport.objects.create(
        employee=employee,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        timestamp_ms=timestamp_ms,
        recorded_at=recorded_at,
    )

    return JsonResponse(
        {
            "id": report.id,
            "status": "created",
        },
        status=201,
    )


@csrf_exempt
def create_employee(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST is allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    last_name = (payload.get("last_name") or "").strip()
    first_name = (payload.get("first_name") or "").strip()
    position_id = payload.get("position_id")

    if not last_name or not first_name or position_id is None:
        return JsonResponse({"error": "last_name, first_name, position_id are required"}, status=400)

    try:
        position_id = _parse_int(position_id, "position_id")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        position = Position.objects.get(id=position_id)
    except Position.DoesNotExist:
        return JsonResponse({"error": "Position not found"}, status=404)

    employee = Employee.objects.create(
        last_name=last_name,
        first_name=first_name,
        position=position,
    )

    return JsonResponse({"id": employee.id, "status": "created"}, status=201)


@csrf_exempt
def update_employee(request, employee_id: int):
    if request.method != "PUT":
        return JsonResponse({"error": "Only PUT is allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    employee = get_object_or_404(Employee, id=employee_id)

    last_name = payload.get("last_name")
    first_name = payload.get("first_name")
    position_id = payload.get("position_id")

    if last_name is not None:
        employee.last_name = str(last_name).strip()
    if first_name is not None:
        employee.first_name = str(first_name).strip()
    if position_id is not None:
        try:
            position_id = _parse_int(position_id, "position_id")
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        try:
            employee.position = Position.objects.get(id=position_id)
        except Position.DoesNotExist:
            return JsonResponse({"error": "Position not found"}, status=404)

    if not employee.last_name or not employee.first_name or not employee.position_id:
        return JsonResponse({"error": "last_name, first_name, position_id cannot be empty"}, status=400)

    employee.save()
    return JsonResponse({"id": employee.id, "status": "updated"}, status=200)


def list_positions(request):
    if request.method != "GET":
        return JsonResponse({"error": "Only GET is allowed"}, status=405)

    positions = list(Position.objects.order_by("id").values("id", "name"))
    return JsonResponse(positions, safe=False, status=200)


class DashboardLoginView(LoginView):
    template_name = "dashboard/login.html"


class DashboardLogoutView(LogoutView):
    pass


@login_required
def dashboard_home(request):
    return redirect("dashboard_zones")


@login_required
def zone_list(request):
    zones = Zone.objects.order_by("-created_at")
    return render(request, "dashboard/zones_list.html", {"zones": zones})


@login_required
def zone_create(request):
    if request.method == "POST":
        form = ZoneForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("dashboard_zones")
    else:
        form = ZoneForm()
    return render(request, "dashboard/zone_form.html", {"form": form, "zone": None})


@login_required
def zone_edit(request, zone_id: int):
    zone = get_object_or_404(Zone, id=zone_id)
    if request.method == "POST":
        form = ZoneForm(request.POST, instance=zone)
        if form.is_valid():
            form.save()
            return redirect("dashboard_zones")
    else:
        form = ZoneForm(instance=zone)
    return render(request, "dashboard/zone_form.html", {"form": form, "zone": zone})


@login_required
def position_list(request):
    positions = Position.objects.order_by("id")
    return render(request, "dashboard/positions_list.html", {"positions": positions})


@login_required
def position_create(request):
    if request.method == "POST":
        form = PositionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("dashboard_positions")
    else:
        form = PositionForm()
    return render(request, "dashboard/position_form.html", {"form": form, "position": None})


@login_required
def position_edit(request, position_id: int):
    position = get_object_or_404(Position, id=position_id)
    if request.method == "POST":
        form = PositionForm(request.POST, instance=position)
        if form.is_valid():
            form.save()
            return redirect("dashboard_positions")
    else:
        form = PositionForm(instance=position)
    return render(request, "dashboard/position_form.html", {"form": form, "position": position})


@login_required
def position_delete(request, position_id: int):
    position = get_object_or_404(Position, id=position_id)
    if request.method == "POST":
        position.delete()
        return redirect("dashboard_positions")
    return render(request, "dashboard/position_delete.html", {"position": position})


@login_required
def report_view(request):
    result = None
    summary = None
    route_in = None
    route_out = None
    route_points = None
    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            employee = form.cleaned_data["employee"]
            zone = form.cleaned_data["zone"]
            start_dt = form.cleaned_data["start_datetime"]
            end_dt = form.cleaned_data["end_datetime"]
            result = build_zone_report(zone, start_dt, end_dt, employee=employee)
            in_segments, out_segments, all_points = load_route_segments(zone, start_dt, end_dt, employee=employee)
            summary = {
                "accounted_hours": result.accounted_seconds / 3600,
                "in_zone_hours": result.in_zone_seconds / 3600,
                "out_zone_hours": result.out_zone_seconds / 3600,
                "in_zone_percent": result.in_zone_percent,
            }
            route_in = json.dumps(in_segments)
            route_out = json.dumps(out_segments)
            route_points = json.dumps(all_points)
    else:
        form = ReportForm()
    return render(
        request,
        "dashboard/report.html",
        {
            "form": form,
            "result": result,
            "summary": summary,
            "route_in": route_in,
            "route_out": route_out,
            "route_points": route_points,
        },
    )

# Create your views here.
