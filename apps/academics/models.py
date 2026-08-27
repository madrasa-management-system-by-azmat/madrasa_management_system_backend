from django.db import models


class Subject(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="subjects", null=True, blank=True)
    name = models.CharField(max_length=150)
    academic_class = models.ForeignKey("students.AcademicClass", on_delete=models.CASCADE, related_name="subjects")
    total_marks = models.PositiveIntegerField(default=100)
    passing_marks = models.PositiveIntegerField(default=40)

    class Meta:
        ordering = ["academic_class__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["academic_class", "name"], name="unique_subject_per_class")
        ]

    def __str__(self):
        return self.name
