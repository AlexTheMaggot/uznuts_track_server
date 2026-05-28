import json
from datetime import datetime, timezone

from django.test import TestCase

from .models import Employee, LocationReport, Position, Zone
from .services import build_daily_employee_zone_report, build_zone_report


class EmployeeZoneReportTests(TestCase):
    def setUp(self):
        self.position = Position.objects.create(name="Driver")
        self.employee = Employee.objects.create(
            last_name="Karimov",
            first_name="Aziz",
            position=self.position,
        )
        self.zone = Zone.objects.create(
            name="Warehouse",
            polygon=json.dumps([[-1, -1], [-1, 1], [1, 1], [1, -1]]),
        )

    def _create_location(self, latitude, longitude, recorded_at):
        return LocationReport.objects.create(
            employee=self.employee,
            latitude=latitude,
            longitude=longitude,
            accuracy=None,
            timestamp_ms=int(recorded_at.timestamp() * 1000),
            recorded_at=recorded_at,
        )

    def test_daily_employee_report_splits_accounted_time_by_days(self):
        start_dt = datetime(2024, 1, 1, 23, 45, tzinfo=timezone.utc)
        end_dt = datetime(2024, 1, 2, 0, 15, tzinfo=timezone.utc)
        self._create_location(0, 0, datetime(2024, 1, 1, 23, 50, tzinfo=timezone.utc))
        self._create_location(2, 2, datetime(2024, 1, 2, 0, 10, tzinfo=timezone.utc))

        summary = build_zone_report(self.zone, start_dt, end_dt, employee=self.employee)
        daily_report = build_daily_employee_zone_report(self.zone, start_dt, end_dt, self.employee)

        self.assertEqual(summary.accounted_seconds, 30 * 60)
        self.assertEqual(summary.in_zone_seconds, 25 * 60)
        self.assertEqual(summary.out_zone_seconds, 5 * 60)
        self.assertEqual(len(daily_report), 2)
        self.assertEqual(daily_report[0].date.isoformat(), "2024-01-01")
        self.assertEqual(daily_report[0].accounted_seconds, 15 * 60)
        self.assertEqual(daily_report[0].in_zone_seconds, 15 * 60)
        self.assertEqual(daily_report[0].out_zone_seconds, 0)
        self.assertEqual(daily_report[1].date.isoformat(), "2024-01-02")
        self.assertEqual(daily_report[1].accounted_seconds, 15 * 60)
        self.assertEqual(daily_report[1].in_zone_seconds, 10 * 60)
        self.assertEqual(daily_report[1].out_zone_seconds, 5 * 60)
