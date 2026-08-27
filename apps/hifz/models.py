from django.db import models


class HifzDailyLog(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="hifz_logs", null=True, blank=True)
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="hifz_logs")
    date = models.DateField()
    sabaq_portion = models.CharField(max_length=255, blank=True)
    sabaqi_portion = models.CharField(max_length=255, blank=True)
    manzil_portion = models.CharField(max_length=255, blank=True)
    verified_by = models.ForeignKey(
        "staff.Staff",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="verified_hifz_logs",
    )

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["student", "date"], name="unique_hifz_log_per_student_day")
        ]
