from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import InternalExam, InternalExamResult, WafaqBoardRegistration, WafaqResult
from .serializers import InternalExamResultSerializer, InternalExamSerializer, WafaqBoardRegistrationSerializer, WafaqResultSerializer
from apps.users.tenancy import TenantScopedViewSetMixin


@extend_schema(tags=["Exams"])
class InternalExamViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = InternalExam.objects.select_related("academic_class", "subject").prefetch_related("classes", "subjects", "papers__subject__academic_class")
    serializer_class = InternalExamSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "academic_class__name", "subject__name"]
    ordering_fields = ["exam_date", "name"]

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        exam = self.get_object()
        class_id = request.query_params.get("academic_class")
        classes = exam.classes.all()
        if not classes.exists() and exam.academic_class_id:
            classes = [exam.academic_class]
        if class_id:
            classes = [academic_class for academic_class in classes if str(academic_class.id) == str(class_id)]
        if not classes:
            return Response({"detail": "No matching class found for this exam."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.students.models import Student
        students = Student.objects.filter(madrasa=self.get_madrasa(), status="active", current_class__in=classes).select_related("current_class")
        subjects = list(exam.subjects.all())
        if not subjects and exam.subject_id:
            subjects = [exam.subject]
        results = InternalExamResult.objects.filter(madrasa=self.get_madrasa(), exam=exam, student__in=students, subject__in=subjects).select_related("student", "subject")
        by_student = {}
        for result in results:
            by_student.setdefault(result.student_id, {})[result.subject_id] = result

        rows = []
        total_marks = sum(subject.total_marks for subject in subjects)
        total_passing_marks = sum(subject.passing_marks for subject in subjects)
        for student in students:
            subject_rows = []
            obtained = 0
            is_complete = True
            is_pass = True
            student_results = by_student.get(student.id, {})
            for subject in subjects:
                result = student_results.get(subject.id)
                marks = result.marks if result else None
                if marks is None:
                    is_complete = False
                    is_pass = False
                else:
                    obtained += marks
                    if marks < subject.passing_marks:
                        is_pass = False
                subject_rows.append({"subject": subject.id, "subject_name": subject.name, "total_marks": subject.total_marks, "passing_marks": subject.passing_marks, "marks": marks, "result": result.result if result else "pending"})
            rows.append({"student": student.id, "student_name": student.full_name, "registration_number": student.registration_number, "class_name": student.current_class.name, "subjects": subject_rows, "obtained_marks": obtained, "total_marks": total_marks, "passing_marks": total_passing_marks, "percentage": round((obtained / total_marks * 100), 2) if total_marks else 0, "result": "pass" if is_complete and is_pass else "fail" if is_complete else "pending"})
        return Response({"exam": exam.id, "exam_name": exam.name, "exam_date": exam.exam_date, "subjects": [{"id": subject.id, "name": subject.name, "total_marks": subject.total_marks, "passing_marks": subject.passing_marks} for subject in subjects], "students": rows})


@extend_schema(tags=["Exams"])
class InternalExamResultViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = InternalExamResult.objects.select_related("exam", "student")
    serializer_class = InternalExamResultSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["marks", "result"]


@extend_schema(tags=["Exams"])
class WafaqBoardRegistrationViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = WafaqBoardRegistration.objects.select_related("student")
    serializer_class = WafaqBoardRegistrationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["student__full_name", "wafaq_name", "roll_number", "status"]
    ordering_fields = ["id", "status"]


@extend_schema(tags=["Exams"])
class WafaqResultViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = WafaqResult.objects.select_related("registration__student")
    serializer_class = WafaqResultSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["passing_year", "result"]
