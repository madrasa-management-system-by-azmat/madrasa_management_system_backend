from drf_spectacular.utils import extend_schema
from django.db import transaction
from django.db.models import Avg, Q
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.users.rbac import user_has_permission

from .models import AnnualResult, ExamAttendance, ExamDuty, ExamResultChange, InternalExam, InternalExamResult, WafaqBoardRegistration, WafaqResult
from .serializers import AnnualResultSerializer, ExamAttendanceSerializer, ExamDutySerializer, ExamResultChangeSerializer, InternalExamResultSerializer, InternalExamSerializer, WafaqBoardRegistrationSerializer, WafaqResultSerializer
from apps.users.tenancy import TenantScopedViewSetMixin


@extend_schema(tags=["Exams"])
class InternalExamViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = InternalExam.objects.select_related("academic_class", "subject").prefetch_related("classes", "subjects", "papers__subject__academic_class")
    serializer_class = InternalExamSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "academic_class__name", "subject__name"]
    ordering_fields = ["exam_date", "name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        academic_year = self.request.query_params.get("academic_year")
        exam_status = self.request.query_params.get("status")
        exam_type = self.request.query_params.get("exam_type")
        if academic_year: queryset = queryset.filter(academic_year_id=academic_year)
        if exam_status: queryset = queryset.filter(status=exam_status)
        if exam_type: queryset = queryset.filter(exam_type=exam_type)
        return queryset

    def _completion_counts(self, exam):
        from apps.students.models import Student, StudentEnrollment

        class_ids = set(exam.classes.values_list("id", flat=True))
        if exam.academic_class_id:
            class_ids.add(exam.academic_class_id)
        subject_ids = set(exam.subjects.values_list("id", flat=True))
        if exam.subject_id:
            subject_ids.add(exam.subject_id)
        if exam.academic_year_id:
            student_ids = set(StudentEnrollment.objects.filter(
                madrasa=self.get_madrasa(), academic_year=exam.academic_year,
                academic_class_id__in=class_ids,
            ).values_list("student_id", flat=True))
        else:
            student_ids = set(Student.objects.filter(
                madrasa=self.get_madrasa(), status=Student.Status.ACTIVE,
                current_class_id__in=class_ids,
            ).values_list("id", flat=True))
        expected_pairs = {(student_id, subject_id) for student_id in student_ids for subject_id in subject_ids}
        results = exam.results.filter(student_id__in=student_ids, subject_id__in=subject_ids)
        actual_pairs = set(results.values_list("student_id", "subject_id"))
        return {
            "students": len(student_ids),
            "subjects": len(subject_ids),
            "missing": len(expected_pairs - actual_pairs),
            "pending": results.filter(result=InternalExamResult.Result.PENDING).count(),
            "unverified": results.filter(verified_at__isnull=True).count(),
        }

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        exam = self.get_object()
        if exam.status in [InternalExam.Status.FINALIZED, InternalExam.Status.PUBLISHED, InternalExam.Status.CANCELLED]:
            return Response({"detail": "This examination cannot be verified in its current state."}, status=status.HTTP_400_BAD_REQUEST)
        counts = self._completion_counts(exam)
        if not counts["students"] or not counts["subjects"] or counts["missing"] or counts["pending"] or counts["unverified"]:
            return Response({"detail": "Complete and verify every student result first.", **counts}, status=status.HTTP_400_BAD_REQUEST)
        exam.status = InternalExam.Status.VERIFIED
        exam.save(update_fields=["status"])
        return Response(self.get_serializer(exam).data)

    @action(detail=True, methods=["post"])
    def finalize(self, request, pk=None):
        if not user_has_permission(request.user, "exams.finalize"):
            return Response({"detail": "You do not have permission to finalize examinations."}, status=status.HTTP_403_FORBIDDEN)
        exam = self.get_object()
        if exam.status != InternalExam.Status.VERIFIED:
            return Response({"detail": "Verify the examination before finalizing it."}, status=status.HTTP_400_BAD_REQUEST)
        counts = self._completion_counts(exam)
        if not counts["students"] or not counts["subjects"] or counts["missing"] or counts["pending"] or counts["unverified"]:
            return Response({"detail": "Every expected result must exist and be verified.", **counts}, status=status.HTTP_400_BAD_REQUEST)
        exam.status = InternalExam.Status.FINALIZED
        exam.finalized_by = request.user
        exam.finalized_at = timezone.now()
        exam.save(update_fields=["status", "finalized_by", "finalized_at"])
        return Response(self.get_serializer(exam).data)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        if not user_has_permission(request.user, "exams.finalize"):
            return Response({"detail": "You do not have permission to publish examinations."}, status=status.HTTP_403_FORBIDDEN)
        exam = self.get_object()
        if exam.status != InternalExam.Status.FINALIZED:
            return Response({"detail": "Finalize the examination before publishing."}, status=status.HTTP_400_BAD_REQUEST)
        exam.status = InternalExam.Status.PUBLISHED
        exam.published_at = timezone.now()
        exam.save(update_fields=["status", "published_at"])
        return Response(self.get_serializer(exam).data)

    def perform_destroy(self, instance):
        if instance.status in [InternalExam.Status.FINALIZED, InternalExam.Status.PUBLISHED]:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Finalized examinations cannot be deleted.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        exam = self.get_object()
        results = exam.results.select_related("student", "subject", "paper")
        subjects = list(exam.subjects.all())
        if exam.subject_id and all(subject.pk != exam.subject_id for subject in subjects):
            subjects.append(exam.subject)
        subject_rows = []
        for subject in subjects:
            rows = results.filter(subject=subject, is_exempt=False)
            total = rows.count()
            passed = rows.filter(result=InternalExamResult.Result.PASS).count()
            subject_rows.append({"subject": subject.id, "name": subject.name, "average": round(float(rows.aggregate(value=Avg("marks"))["value"] or 0), 2), "pass_rate": round(passed / total * 100, 1) if total else 0, "students": total})
        student_totals = {}
        for row in results:
            if row.is_exempt:
                continue
            item = student_totals.setdefault(row.student_id, {"student": row.student_id, "name": row.student.full_name, "obtained": 0, "total": 0, "all_passed": True})
            item["obtained"] += float(row.marks)
            item["total"] += row.paper.total_marks_snapshot if row.paper and row.paper.total_marks_snapshot is not None else row.subject.total_marks if row.subject else 0
            item["all_passed"] = item["all_passed"] and row.result == InternalExamResult.Result.PASS
        ranking = sorted([{**item, "percentage": round(item["obtained"] / item["total"] * 100, 2) if item["total"] else 0} for item in student_totals.values()], key=lambda item: item["percentage"], reverse=True)
        for index, item in enumerate(ranking, 1): item["rank"] = index
        return Response({"exam": self.get_serializer(exam).data, "subjects": subject_rows, "students": ranking, "overview": {"students": len(ranking), "pass_rate": round(sum(item["all_passed"] for item in ranking) / len(ranking) * 100, 1) if ranking else 0, "average_percentage": round(sum(item["percentage"] for item in ranking) / len(ranking), 2) if ranking else 0, "weak_subjects": sorted(subject_rows, key=lambda item: item["pass_rate"])[:3]}})

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
        subjects = list(exam.subjects.filter(academic_class__in=classes))
        if not subjects and exam.subject_id and exam.subject.academic_class_id in [academic_class.id for academic_class in classes]:
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
            student_results = by_student.get(student.id, {})
            for subject in subjects:
                result = student_results.get(subject.id)
                marks = result.marks if result else None
                if marks is None:
                    is_complete = False
                else:
                    obtained += marks
                subject_rows.append({"subject": subject.id, "subject_name": subject.name, "total_marks": subject.total_marks, "passing_marks": subject.passing_marks, "marks": marks, "result": result.result if result else "pending"})
            all_subjects_passed = all(row["result"] == "pass" for row in subject_rows)
            overall_result = "pending" if not is_complete else "pass" if all_subjects_passed else "fail"
            rows.append({"student": student.id, "student_name": student.full_name, "registration_number": student.registration_number, "class_name": student.current_class.name, "subjects": subject_rows, "obtained_marks": obtained, "total_marks": total_marks, "passing_marks": total_passing_marks, "percentage": round((obtained / total_marks * 100), 2) if total_marks else 0, "result": overall_result})
        return Response({"exam": exam.id, "exam_name": exam.name, "exam_date": exam.exam_date, "subjects": [{"id": subject.id, "name": subject.name, "total_marks": subject.total_marks, "passing_marks": subject.passing_marks} for subject in subjects], "students": rows})


@extend_schema(tags=["Exams"])
class InternalExamResultViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = InternalExamResult.objects.select_related("exam", "student")
    serializer_class = InternalExamResultSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["marks", "result"]

    def perform_create(self, serializer):
        from apps.students.models import StudentEnrollment
        exam, student = serializer.validated_data["exam"], serializer.validated_data["student"]
        class_ids = set(exam.classes.values_list("id", flat=True))
        if exam.academic_class_id:
            class_ids.add(exam.academic_class_id)
        enrollment = StudentEnrollment.objects.filter(
            madrasa=self.get_madrasa(), student=student, academic_year=exam.academic_year,
            academic_class_id__in=class_ids,
        ).first() if exam.academic_year_id else None
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), entered_by=self.request.user, enrollment=enrollment, roll_number_snapshot=enrollment.roll_number if enrollment else "")

    def perform_destroy(self, instance):
        if instance.exam.status in [InternalExam.Status.FINALIZED, InternalExam.Status.PUBLISHED]:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Finalized examination results are locked.")
        super().perform_destroy(instance)

    def update(self, request, *args, **kwargs):
        result = self.get_object()
        if result.exam.status in [InternalExam.Status.FINALIZED, InternalExam.Status.PUBLISHED]:
            return Response({"detail": "Finalized examination results are locked."}, status=status.HTTP_400_BAD_REQUEST)
        requested_marks = request.data.get("marks", result.marks)
        marks_changed = str(requested_marks) != str(result.marks)
        reason = str(request.data.get("change_reason", "")).strip()
        if marks_changed and not reason:
            return Response({"change_reason": ["A reason is required when changing marks."]}, status=status.HTTP_400_BAD_REQUEST)
        old_marks, old_result = result.marks, result.result
        response = super().update(request, *args, **kwargs)
        result.refresh_from_db()
        if old_marks != result.marks or old_result != result.result:
            ExamResultChange.objects.create(madrasa=self.get_madrasa(), result=result, old_marks=old_marks, new_marks=result.marks, old_result=old_result, new_result=result.result, reason=reason or "Result status updated", changed_by=request.user)
        return response

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        result = self.get_object()
        if result.exam.status in [InternalExam.Status.FINALIZED, InternalExam.Status.PUBLISHED]:
            return Response({"detail": "Finalized examination results are locked."}, status=status.HTTP_400_BAD_REQUEST)
        result.verified_by = request.user
        result.verified_at = timezone.now()
        result.save(update_fields=["verified_by", "verified_at"])
        return Response(self.get_serializer(result).data)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        return Response(ExamResultChangeSerializer(self.get_object().changes.select_related("changed_by"), many=True).data)


@extend_schema(tags=["Exam Control"])
class ExamDutyViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = ExamDuty.objects.select_related("exam", "paper__subject", "staff")
    serializer_class = ExamDutySerializer
    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), assigned_by=self.request.user)


@extend_schema(tags=["Exam Control"])
class ExamAttendanceViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = ExamAttendance.objects.select_related("paper__subject", "enrollment__student")
    serializer_class = ExamAttendanceSerializer
    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), marked_by=self.request.user)


@extend_schema(tags=["Exam Control"])
class AnnualResultViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AnnualResult.objects.select_related("enrollment__student", "enrollment__academic_class", "enrollment__academic_year")
    serializer_class = AnnualResultSerializer

    @action(detail=False, methods=["post"])
    def generate(self, request):
        from apps.students.models import StudentEnrollment
        year_id, class_id = request.data.get("academic_year"), request.data.get("academic_class")
        enrollments = StudentEnrollment.objects.filter(madrasa=self.get_madrasa(), academic_year_id=year_id, academic_class_id=class_id)
        exams = InternalExam.objects.filter(
            Q(classes__id=class_id) | Q(academic_class_id=class_id),
            madrasa=self.get_madrasa(), academic_year_id=year_id,
            status__in=[InternalExam.Status.FINALIZED, InternalExam.Status.PUBLISHED],
        ).distinct()
        generated = []
        for enrollment in enrollments:
            rows = InternalExamResult.objects.filter(madrasa=self.get_madrasa(), exam__in=exams, student=enrollment.student).select_related("subject", "paper")
            total = sum(
                row.paper.total_marks_snapshot if row.paper and row.paper.total_marks_snapshot is not None else row.subject.total_marks
                for row in rows if row.subject and not row.is_exempt
            )
            obtained = sum(row.marks for row in rows if not row.is_absent and not row.is_exempt)
            complete = rows.exists() and all(row.result != InternalExamResult.Result.PENDING for row in rows)
            passed = complete and all(row.result == InternalExamResult.Result.PASS for row in rows)
            percentage = obtained / total * 100 if total else 0
            grade = "A+" if percentage >= 80 else "A" if percentage >= 70 else "B" if percentage >= 60 else "C" if percentage >= 50 else "D" if passed else "F"
            annual, _ = AnnualResult.objects.update_or_create(madrasa=self.get_madrasa(), enrollment=enrollment, defaults={"total_marks": total, "obtained_marks": obtained, "percentage": percentage, "grade": grade, "result": InternalExamResult.Result.PASS if passed else InternalExamResult.Result.FAIL if complete else InternalExamResult.Result.PENDING, "promotion_eligible": passed, "finalized_by": request.user, "finalized_at": timezone.now()})
            generated.append(annual)
        ranking = sorted(generated, key=lambda item: item.percentage, reverse=True)
        for rank, annual in enumerate(ranking, 1):
            annual.rank = rank
            annual.save(update_fields=["rank"])
        return Response(self.get_serializer(ranking, many=True).data)


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
