from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.rbac import effective_permissions
from apps.users.tenancy import current_madrasa

REPORTS = [
    {"key": "student-directory", "title": "طلبہ ڈائریکٹری", "description": "فعال طلبہ، جماعت، حلقہ اور رابطہ", "permission": "students.view", "filters": ["status", "class_id"]},
    {"key": "attendance-summary", "title": "حاضری خلاصہ", "description": "تاریخ وار حاضر، غیر حاضر، رخصت اور تناسب", "permission": "attendance.view", "filters": ["date_from", "date_to", "class_id"]},
    {"key": "exam-performance", "title": "امتحانی کارکردگی", "description": "امتحان وار طلبہ کے نمبر، نتیجہ اور اوسط", "permission": "exams.view", "filters": ["exam_id", "class_id"]},
    {"key": "finance-summary", "title": "مالی خلاصہ", "description": "فیس، عطیات، اخراجات اور خالص رقم", "permission": "finance.view", "filters": ["date_from", "date_to"]},
    {"key": "library-circulation", "title": "لائبریری گردش", "description": "جاری، واپس، تاخیر اور رکن کی تفصیل", "permission": "library.view", "filters": ["date_from", "date_to"]},
    {"key": "leave-register", "title": "رخصت رجسٹر", "description": "عملہ و طلبہ رخصت درخواستیں اور دن", "permission": "leaves.view", "filters": ["date_from", "date_to", "status"]},
    {"key": "inventory-status", "title": "اسٹاک صورتحال", "description": "موجودہ مقدار، کم اسٹاک اور مالیت", "permission": "operations.view", "filters": []},
]


def parse_date(value, fallback):
    try:
        return date.fromisoformat(value) if value else fallback
    except ValueError:
        return fallback


def payload(report, columns, rows, summary=None, meta=None):
    return {"report": report, "generated_at": timezone.now(), "columns": columns, "rows": rows, "summary": summary or [], "meta": meta or {}}


class ReportCatalogueAPIView(APIView):
    def get(self, request):
        permissions = effective_permissions(request.user)
        return Response([item for item in REPORTS if item["permission"] in permissions])


class ReportGenerateAPIView(APIView):
    def get(self, request, report_key):
        definition = next((item for item in REPORTS if item["key"] == report_key), None)
        if not definition:
            return Response({"detail": "Unknown report."}, status=404)
        if definition["permission"] not in effective_permissions(request.user):
            return Response({"detail": "You do not have permission to view this report."}, status=403)
        tenant = current_madrasa(request)
        today = timezone.localdate()
        date_from = parse_date(request.query_params.get("date_from"), today.replace(day=1))
        date_to = parse_date(request.query_params.get("date_to"), today)
        if date_from > date_to:
            return Response({"detail": "Start date must not be after end date."}, status=400)

        if report_key == "student-directory":
            from apps.students.models import Student
            rows = Student.objects.filter(madrasa=tenant).select_related("current_class", "current_halaqa")
            status_value = request.query_params.get("status", "active")
            if status_value != "all": rows = rows.filter(status=status_value)
            if request.query_params.get("class_id"): rows = rows.filter(current_class_id=request.query_params["class_id"])
            data = [{"registration_number": x.registration_number, "name": x.full_name, "guardian": x.guardian_name, "class": x.current_class.name, "halaqa": x.current_halaqa.name if x.current_halaqa else "—", "phone": x.guardian_phone or x.phone, "status": x.get_status_display()} for x in rows.order_by("current_class__name", "full_name")]
            return Response(payload(definition, [{"key":"registration_number","label":"رجسٹریشن"},{"key":"name","label":"طالب علم"},{"key":"guardian","label":"سرپرست"},{"key":"class","label":"جماعت"},{"key":"halaqa","label":"حلقہ"},{"key":"phone","label":"رابطہ"},{"key":"status","label":"حیثیت"}], data, [{"label":"کل طلبہ","value":len(data)}]))

        if report_key == "attendance-summary":
            from apps.students.models import StudentAttendance
            query = StudentAttendance.objects.filter(madrasa=tenant, date__range=(date_from, date_to)).select_related("student", "student__current_class")
            if request.query_params.get("class_id"): query = query.filter(student__current_class_id=request.query_params["class_id"])
            grouped = query.values("student_id", "student__registration_number", "student__full_name", "student__current_class__name").annotate(total=Count("id"), present=Count("id", filter=Q(status="present")), absent=Count("id", filter=Q(status="absent")), leave=Count("id", filter=Q(status="leave")), late=Count("id", filter=Q(status="late"))).order_by("student__full_name")
            data = [{"registration_number":x["student__registration_number"],"name":x["student__full_name"],"class":x["student__current_class__name"],"present":x["present"],"absent":x["absent"],"leave":x["leave"],"late":x["late"],"percentage":round(x["present"] / x["total"] * 100, 1) if x["total"] else 0} for x in grouped]
            totals = query.values("status").annotate(count=Count("id")); total_map={x["status"]:x["count"] for x in totals}
            return Response(payload(definition,[{"key":"registration_number","label":"رجسٹریشن"},{"key":"name","label":"طالب علم"},{"key":"class","label":"جماعت"},{"key":"present","label":"حاضر"},{"key":"absent","label":"غیر حاضر"},{"key":"leave","label":"رخصت"},{"key":"late","label":"تاخیر"},{"key":"percentage","label":"فیصد"}],data,[{"label":"حاضر","value":total_map.get("present",0)},{"label":"غیر حاضر","value":total_map.get("absent",0)},{"label":"کل اندراج","value":sum(total_map.values())}],{"date_from":date_from,"date_to":date_to}))

        if report_key == "exam-performance":
            from apps.exams.models import InternalExam, InternalExamResult
            exam_id=request.query_params.get("exam_id")
            if not exam_id:return Response({"detail":"Select an examination."},status=400)
            exam=InternalExam.objects.filter(madrasa=tenant,pk=exam_id).first()
            if not exam:return Response({"detail":"Examination not found."},status=404)
            query=InternalExamResult.objects.filter(madrasa=tenant,exam=exam).select_related("student","subject")
            if request.query_params.get("class_id"):query=query.filter(student__current_class_id=request.query_params["class_id"])
            data=[{"student":x.student.full_name,"registration_number":x.student.registration_number,"subject":x.subject.name if x.subject else "—","marks":x.marks,"result":x.get_result_display(),"verified":"ہاں" if x.verified_at else "نہیں"} for x in query.order_by("student__full_name","subject__name")]
            passed=query.filter(result="pass").count();total=query.count()
            return Response(payload(definition,[{"key":"registration_number","label":"رجسٹریشن"},{"key":"student","label":"طالب علم"},{"key":"subject","label":"مضمون"},{"key":"marks","label":"نمبر"},{"key":"result","label":"نتیجہ"},{"key":"verified","label":"تصدیق"}],data,[{"label":"کل نتائج","value":total},{"label":"کامیاب","value":passed},{"label":"کامیابی فیصد","value":round(passed/total*100,1) if total else 0}],{"exam":exam.name}))

        if report_key == "finance-summary":
            from apps.finance.models import Donation, Expense, StudentFeePayment
            fee=StudentFeePayment.objects.filter(madrasa=tenant,payment_date__range=(date_from,date_to)).aggregate(total=Coalesce(Sum("amount"),Decimal("0")))["total"]
            donations=Donation.objects.filter(madrasa=tenant,date__range=(date_from,date_to)).aggregate(total=Coalesce(Sum("amount"),Decimal("0")))["total"]
            expenses=Expense.objects.filter(madrasa=tenant,date__range=(date_from,date_to)).values("date","title","fund__name").annotate(amount=Sum("amount")).order_by("-date")
            data=[{"date":x["date"],"description":x["title"],"fund":x["fund__name"],"amount":x["amount"]} for x in expenses]
            expense_total=sum((x["amount"] for x in expenses),Decimal("0"));income=fee+donations
            return Response(payload(definition,[{"key":"date","label":"تاریخ"},{"key":"description","label":"خرچ"},{"key":"fund","label":"فنڈ"},{"key":"amount","label":"رقم"}],data,[{"label":"فیس وصولی","value":fee},{"label":"عطیات","value":donations},{"label":"اخراجات","value":expense_total},{"label":"خالص","value":income-expense_total}],{"date_from":date_from,"date_to":date_to}))

        if report_key == "library-circulation":
            from apps.library.models import LibraryLoan
            query=LibraryLoan.objects.filter(madrasa=tenant,issued_on__range=(date_from,date_to)).select_related("copy__book","member__student","member__staff")
            data=[{"book":x.copy.book.title,"member":x.member.display_name,"issued_on":x.issued_on,"due_on":x.due_on,"returned_on":x.returned_on or "—","status":"تاخیر" if not x.returned_on and x.due_on<today else x.get_status_display()} for x in query]
            return Response(payload(definition,[{"key":"book","label":"کتاب"},{"key":"member","label":"رکن"},{"key":"issued_on","label":"اجرا"},{"key":"due_on","label":"واپسی تاریخ"},{"key":"returned_on","label":"واپس ہوئی"},{"key":"status","label":"حیثیت"}],data,[{"label":"کل اجرا","value":len(data)},{"label":"زیر گردش","value":query.filter(returned_on__isnull=True).count()},{"label":"تاخیر","value":query.filter(returned_on__isnull=True,due_on__lt=today).count()}],{"date_from":date_from,"date_to":date_to}))

        if report_key == "leave-register":
            from apps.leaves.models import LeaveRequest
            query=LeaveRequest.objects.filter(madrasa=tenant,starts_on__lte=date_to,ends_on__gte=date_from).select_related("staff","student","leave_type")
            if request.query_params.get("status"):query=query.filter(status=request.query_params["status"])
            data=[{"request_number":x.request_number,"person":x.staff.full_name if x.staff_id else x.student.full_name,"type":x.leave_type.name,"from":x.starts_on,"to":x.ends_on,"days":x.chargeable_days,"status":x.get_status_display()} for x in query]
            return Response(payload(definition,[{"key":"request_number","label":"درخواست"},{"key":"person","label":"نام"},{"key":"type","label":"قسم"},{"key":"from","label":"از"},{"key":"to","label":"تا"},{"key":"days","label":"دن"},{"key":"status","label":"حیثیت"}],data,[{"label":"کل درخواستیں","value":len(data)},{"label":"منظور","value":query.filter(status="approved").count()},{"label":"زیر التوا","value":query.filter(status__in=["submitted","pending_approval"]).count()}],{"date_from":date_from,"date_to":date_to}))

        if report_key == "inventory-status":
            from apps.operations.models import InventoryItem
            query=InventoryItem.objects.filter(madrasa=tenant,is_active=True).annotate(quantity=Coalesce(Sum("stock_lots__quantity"),Decimal("0")),value=Coalesce(Sum(ExpressionWrapper(F("stock_lots__quantity")*F("stock_lots__unit_cost"),output_field=DecimalField(max_digits=18,decimal_places=2))),Decimal("0"))).select_related("category")
            data=[{"sku":x.sku,"item":x.name,"category":x.category.name,"quantity":x.quantity,"unit":x.unit,"reorder_level":x.reorder_level,"value":x.value,"status":"کم اسٹاک" if x.quantity<=x.reorder_level else "کافی"} for x in query]
            return Response(payload(definition,[{"key":"sku","label":"SKU"},{"key":"item","label":"شے"},{"key":"category","label":"زمرہ"},{"key":"quantity","label":"مقدار"},{"key":"unit","label":"اکائی"},{"key":"reorder_level","label":"کم حد"},{"key":"value","label":"مالیت"},{"key":"status","label":"حیثیت"}],data,[{"label":"اشیاء","value":len(data)},{"label":"کم اسٹاک","value":sum(1 for x in data if x["status"]=="کم اسٹاک")},{"label":"کل مالیت","value":sum((x["value"] for x in data),Decimal("0"))}]))
