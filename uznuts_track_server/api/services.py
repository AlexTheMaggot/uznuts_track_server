import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from .models import Employee, LocationReport, Zone


def _point_in_polygon(point_lat, point_lng, polygon_points):
    inside = False
    j = len(polygon_points) - 1
    for i, (lat_i, lng_i) in enumerate(polygon_points):
        lat_j, lng_j = polygon_points[j]
        intersects = ((lng_i > point_lng) != (lng_j > point_lng)) and (
            point_lat < (lat_j - lat_i) * (point_lng - lng_i) / (lng_j - lng_i + 1e-12) + lat_i
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _load_polygon(zone: Zone):
    try:
        raw = json.loads(zone.polygon)
    except json.JSONDecodeError:
        return []
    points = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            points.append((float(item[0]), float(item[1])))
    return points


@dataclass
class ReportResult:
    accounted_seconds: float
    in_zone_seconds: float
    out_zone_seconds: float

    @property
    def in_zone_percent(self) -> float:
        if self.accounted_seconds <= 0:
            return 0.0
        return (self.in_zone_seconds / self.accounted_seconds) * 100


@dataclass
class DailyReportResult:
    date: date
    accounted_seconds: float
    in_zone_seconds: float
    out_zone_seconds: float

    @property
    def accounted_hours(self) -> float:
        return self.accounted_seconds / 3600

    @property
    def in_zone_hours(self) -> float:
        return self.in_zone_seconds / 3600

    @property
    def out_zone_hours(self) -> float:
        return self.out_zone_seconds / 3600

    @property
    def in_zone_percent(self) -> float:
        if self.accounted_seconds <= 0:
            return 0.0
        return (self.in_zone_seconds / self.accounted_seconds) * 100


def _build_accounted_intervals(zone: Zone, start_dt: datetime, end_dt: datetime, employee: Optional[Employee] = None):
    start_dt = start_dt.astimezone(timezone.utc)
    end_dt = end_dt.astimezone(timezone.utc)
    if end_dt <= start_dt:
        return []

    points = _load_polygon(zone)
    if not points:
        return []

    qs = LocationReport.objects.filter(recorded_at__gte=start_dt, recorded_at__lte=end_dt)
    if employee is not None:
        qs = qs.filter(employee=employee)
    reports = list(qs.order_by("recorded_at").values("latitude", "longitude", "recorded_at"))

    if not reports:
        return []

    intervals = []

    def is_in_zone(item):
        return _point_in_polygon(item["latitude"], item["longitude"], points)

    def add_interval(interval_start: datetime, interval_end: datetime, in_zone_flag: bool):
        clipped_start = max(interval_start, start_dt)
        clipped_end = min(interval_end, end_dt)
        if clipped_end > clipped_start:
            intervals.append((clipped_start, clipped_end, in_zone_flag))

    start_gap = (reports[0]["recorded_at"] - start_dt).total_seconds()
    if start_gap > 0:
        accounted_start = start_gap if start_gap <= 600 else 600
        add_interval(
            reports[0]["recorded_at"] - timedelta(seconds=accounted_start),
            reports[0]["recorded_at"],
            is_in_zone(reports[0]),
        )

    for current, next_item in zip(reports, reports[1:]):
        interval = (next_item["recorded_at"] - current["recorded_at"]).total_seconds()
        if interval <= 0:
            continue
        if interval > 600:
            accounted_interval = max(interval - 1200, 0.0)
            interval_start = current["recorded_at"] + timedelta(seconds=600)
            interval_end = interval_start + timedelta(seconds=accounted_interval)
        else:
            interval_start = current["recorded_at"]
            interval_end = next_item["recorded_at"]
        add_interval(interval_start, interval_end, is_in_zone(current))

    end_gap = (end_dt - reports[-1]["recorded_at"]).total_seconds()
    if end_gap > 0:
        accounted_end = end_gap if end_gap <= 600 else 600
        add_interval(
            reports[-1]["recorded_at"],
            reports[-1]["recorded_at"] + timedelta(seconds=accounted_end),
            is_in_zone(reports[-1]),
        )

    return intervals


def build_zone_report(zone: Zone, start_dt: datetime, end_dt: datetime, employee: Optional[Employee] = None) -> ReportResult:
    accounted = 0.0
    in_zone = 0.0

    for interval_start, interval_end, in_zone_flag in _build_accounted_intervals(zone, start_dt, end_dt, employee=employee):
        seconds = (interval_end - interval_start).total_seconds()
        accounted += seconds
        if in_zone_flag:
            in_zone += seconds

    out_zone = max(accounted - in_zone, 0.0)
    return ReportResult(accounted, in_zone, out_zone)


def build_daily_employee_zone_report(
    zone: Zone,
    start_dt: datetime,
    end_dt: datetime,
    employee: Employee,
) -> list[DailyReportResult]:
    start_dt = start_dt.astimezone(timezone.utc)
    end_dt = end_dt.astimezone(timezone.utc)
    if end_dt <= start_dt:
        return []

    totals_by_day = {}
    current_day = start_dt.date()
    end_day = end_dt.date()
    while current_day <= end_day:
        day_start = max(start_dt, datetime.combine(current_day, time.min, tzinfo=timezone.utc))
        day_end = min(end_dt, datetime.combine(current_day, time.max, tzinfo=timezone.utc))
        day_result = build_zone_report(zone, day_start, day_end, employee=employee)
        totals_by_day[current_day] = {
            "accounted": day_result.accounted_seconds,
            "in_zone": day_result.in_zone_seconds,
        }
        current_day += timedelta(days=1)

    return [
        DailyReportResult(
            date=day,
            accounted_seconds=values["accounted"],
            in_zone_seconds=values["in_zone"],
            out_zone_seconds=max(values["accounted"] - values["in_zone"], 0.0),
        )
        for day, values in totals_by_day.items()
    ]


def load_route_segments(
    zone: Zone,
    start_dt: datetime,
    end_dt: datetime,
    limit: int = 10000,
    employee: Optional[Employee] = None,
):
    start_dt = start_dt.astimezone(timezone.utc)
    end_dt = end_dt.astimezone(timezone.utc)

    points = _load_polygon(zone)
    if not points:
        return [], [], []

    qs = LocationReport.objects.filter(recorded_at__gte=start_dt, recorded_at__lte=end_dt)
    if employee is not None:
        qs = qs.filter(employee=employee)
    reports = list(qs.order_by("recorded_at").values("latitude", "longitude")[:limit])

    if not reports:
        return [], [], []

    in_segments = []
    out_segments = []
    all_points = []

    # Build segments based on the destination point zone.
    prev_point = None
    prev_in_zone = None
    current_segment = []
    current_color_in_zone = None

    for item in reports:
        lat = item["latitude"]
        lng = item["longitude"]
        current_point = [lat, lng]
        all_points.append(current_point)
        current_in_zone = _point_in_polygon(lat, lng, points)

        if prev_point is None:
            prev_point = current_point
            prev_in_zone = current_in_zone
            continue

        # Color the segment based on the destination point (current_in_zone).
        segment_color_in_zone = current_in_zone

        if current_color_in_zone is None:
            current_color_in_zone = segment_color_in_zone
            current_segment = [prev_point, current_point]
        elif segment_color_in_zone == current_color_in_zone:
            current_segment.append(current_point)
        else:
            if len(current_segment) >= 2:
                if current_color_in_zone:
                    in_segments.append(current_segment)
                else:
                    out_segments.append(current_segment)
            current_color_in_zone = segment_color_in_zone
            current_segment = [prev_point, current_point]

        prev_point = current_point
        prev_in_zone = current_in_zone

    if len(current_segment) >= 2:
        if current_color_in_zone:
            in_segments.append(current_segment)
        else:
            out_segments.append(current_segment)

    return in_segments, out_segments, all_points
