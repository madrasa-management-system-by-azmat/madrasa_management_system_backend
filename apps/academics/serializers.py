from rest_framework import serializers

from .models import Subject


class SubjectSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="academic_class.name", read_only=True)

    def validate(self, attrs):
        total_marks = attrs.get("total_marks", self.instance.total_marks if self.instance else 100)
        passing_marks = attrs.get("passing_marks", self.instance.passing_marks if self.instance else 40)
        if passing_marks > total_marks:
            raise serializers.ValidationError({"passing_marks": "Passing marks cannot exceed total marks."})
        return attrs

    class Meta:
        model = Subject
        fields = ["id", "name", "academic_class", "class_name", "total_marks", "passing_marks"]
