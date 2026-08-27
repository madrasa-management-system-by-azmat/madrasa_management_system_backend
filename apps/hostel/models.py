from django.db import models


class HostelWing(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="hostel_wings", null=True, blank=True)
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class HostelRoom(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="hostel_rooms", null=True, blank=True)
    wing = models.ForeignKey(HostelWing, on_delete=models.CASCADE, related_name="rooms")
    room_number = models.CharField(max_length=30)
    capacity = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["wing__name", "room_number"]
        constraints = [
            models.UniqueConstraint(fields=["wing", "room_number"], name="unique_room_per_wing")
        ]

    def __str__(self):
        return f"{self.wing} - {self.room_number}"


class HostelAllocation(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="hostel_allocations", null=True, blank=True)
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="hostel_allocations")
    room = models.ForeignKey(HostelRoom, on_delete=models.PROTECT, related_name="allocations")
    bed_number = models.CharField(max_length=20)
    allocated_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-allocated_date"]
        constraints = [
            models.UniqueConstraint(fields=["room", "bed_number"], name="unique_bed_per_room")
        ]


class GatePass(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="gate_passes", null=True, blank=True)
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="gate_passes")
    purpose = models.TextField()
    out_date = models.DateTimeField()
    in_date = models.DateTimeField(blank=True, null=True)
    authorized_by = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, related_name="authorized_gate_passes")

    class Meta:
        ordering = ["-out_date"]
