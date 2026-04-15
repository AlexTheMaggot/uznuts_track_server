from django.db import models


class LocationReport(models.Model):
    employee = models.ForeignKey("Employee", on_delete=models.CASCADE, null=True, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    accuracy = models.FloatField(null=True, blank=True)
    timestamp_ms = models.BigIntegerField()
    recorded_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.latitude}, {self.longitude} @ {self.timestamp_ms}"


class Zone(models.Model):
    name = models.CharField(max_length=200)
    polygon = models.TextField(help_text="JSON list of [lat, lng] points")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class Employee(models.Model):
    last_name = models.CharField(max_length=120)
    first_name = models.CharField(max_length=120)
    position = models.ForeignKey("Position", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name} ({self.position.name})"


class Position(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self) -> str:
        return self.name

# Create your models here.
