import json
from dataclasses import dataclass
from datetime import datetime, timezone
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


def build_zone_report(zone: Zone, start_dt: datetime, end_dt: datetime, employee: Optional[Employee] = None) -> ReportResult:
    start_dt = start_dt.astimezone(timezone.utc)
    end_dt = end_dt.astimezone(timezone.utc)

    points = _load_polygon(zone)
    if not points:
        return ReportResult(0.0, 0.0, 0.0)

    qs = LocationReport.objects.filter(recorded_at__gte=start_dt, recorded_at__lte=end_dt)
    if employee is not None:
        qs = qs.filter(employee=employee)
    reports = list(qs.order_by("recorded_at").values("latitude", "longitude", "recorded_at"))

    if not reports:
        return ReportResult(0.0, 0.0, 0.0)

    accounted = 0.0
    in_zone = 0.0

    def add_interval(seconds: float, in_zone_flag: bool):
        nonlocal accounted, in_zone
        if seconds <= 0:
            return
        accounted += seconds
        if in_zone_flag:
            in_zone += seconds

    def is_in_zone(item):
        return _point_in_polygon(item["latitude"], item["longitude"], points)

    # Start gap handling
    start_gap = (reports[0]["recorded_at"] - start_dt).total_seconds()
    if start_gap > 0:
        accounted_start = start_gap if start_gap <= 600 else 600
        add_interval(accounted_start, is_in_zone(reports[0]))

    # Between points
    for current, next_item in zip(reports, reports[1:]):
        interval = (next_item["recorded_at"] - current["recorded_at"]).total_seconds()
        if interval <= 0:
            continue
        if interval > 600:
            interval = max(interval - 1200, 0.0)
        add_interval(interval, is_in_zone(current))

    # End gap handling
    end_gap = (end_dt - reports[-1]["recorded_at"]).total_seconds()
    if end_gap > 0:
        accounted_end = end_gap if end_gap <= 600 else 600
        add_interval(accounted_end, is_in_zone(reports[-1]))

    out_zone = max(accounted - in_zone, 0.0)
    return ReportResult(accounted, in_zone, out_zone)


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
        return [], []

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
