from decimal import Decimal
from django.db import transaction
from django.db.models import F,Sum
from django.utils import timezone
from rest_framework import filters,serializers,status,viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.users.tenancy import TenantScopedViewSetMixin
from apps.users.rbac import user_has_permission
from .models import *
from .serializers import *

class Base(TenantScopedViewSetMixin,viewsets.ModelViewSet):filter_backends=[filters.SearchFilter,filters.OrderingFilter]
class LocationViewSet(Base):queryset=OperationsLocation.objects.all();serializer_class=LocationSerializer
class ItemCategoryViewSet(Base):queryset=ItemCategory.objects.all();serializer_class=ItemCategorySerializer
class ItemViewSet(Base):
 queryset=InventoryItem.objects.select_related("category").prefetch_related("stock_lots");serializer_class=ItemSerializer;search_fields=["sku","name","category__name"]
class StockLotViewSet(Base):queryset=StockLot.objects.select_related("item","location");serializer_class=StockLotSerializer
class StockTransactionViewSet(Base):
 queryset=StockTransaction.objects.select_related("item","location","lot");serializer_class=StockTransactionSerializer
 @transaction.atomic
 def perform_create(self,serializer):
  data=serializer.validated_data;lot=data.get("lot");qty=data["quantity"];kind=data["transaction_type"]
  if lot:
   lot=StockLot.objects.select_for_update().get(pk=lot.pk)
   delta=qty if kind in ["receipt","transfer_in","adjustment"] else -qty
   if lot.quantity+delta<0:raise serializers.ValidationError("Insufficient stock.")
   lot.quantity+=delta;lot.save(update_fields=["quantity"])
  serializer.save(madrasa=self.get_madrasa(),created_by=self.request.user)
class VendorViewSet(Base):queryset=Vendor.objects.all();serializer_class=VendorSerializer;search_fields=["name","phone"]
class PurchaseOrderViewSet(Base):
 queryset=PurchaseOrder.objects.select_related("vendor","location","fund").prefetch_related("lines__item");serializer_class=PurchaseOrderSerializer
 def perform_create(self,serializer):serializer.save(madrasa=self.get_madrasa(),order_number=f"PO-{self.get_madrasa().id}-{timezone.localdate().year}-{PurchaseOrder.objects.filter(madrasa=self.get_madrasa()).count()+1:06d}",created_by=self.request.user)
 @action(detail=True,methods=["post"])
 def submit(self,request,pk=None):
  o=self.get_object();o.status="submitted";o.save(update_fields=["status"]);return Response(self.get_serializer(o).data)
 @action(detail=True,methods=["post"])
 def approve(self,request,pk=None):
  if not user_has_permission(request.user,"operations.manage"):return Response({"detail":"Purchase approval permission required."},status=403)
  o=self.get_object();o.status="approved";o.approved_by=request.user;o.approved_at=timezone.now();o.save(update_fields=["status","approved_by","approved_at"]);return Response(self.get_serializer(o).data)
 @action(detail=True,methods=["post"])
 @transaction.atomic
 def receive(self,request,pk=None):
  o=self.get_object()
  if o.status not in ["approved","part_received"]:return Response({"detail":"Approve the order first."},status=400)
  for line in o.lines.select_for_update():
   receive=Decimal(str(request.data.get("lines",{}).get(str(line.id),line.quantity-line.received_quantity)))
   if receive<=0 or line.received_quantity+receive>line.quantity:continue
   lot,_=StockLot.objects.select_for_update().get_or_create(madrasa=self.get_madrasa(),item=line.item,location=o.location,lot_number=f"{o.order_number}-{line.id}",defaults={"unit_cost":line.unit_price})
   lot.quantity+=receive;lot.save(update_fields=["quantity"]);line.received_quantity+=receive;line.save(update_fields=["received_quantity"])
   StockTransaction.objects.create(madrasa=self.get_madrasa(),item=line.item,location=o.location,lot=lot,transaction_type="receipt",quantity=receive,reference_type="purchase_order",reference_id=o.id,created_by=request.user)
  o.status="received" if all(x.received_quantity>=x.quantity for x in o.lines.all()) else "part_received";o.save(update_fields=["status"]);return Response(self.get_serializer(o).data)
class PurchaseLineViewSet(Base):queryset=PurchaseOrderLine.objects.select_related("order","item");serializer_class=PurchaseLineSerializer
class AssetViewSet(Base):queryset=Asset.objects.select_related("location","custodian","item");serializer_class=AssetSerializer;search_fields=["asset_number","name","serial_number"]
class AssetMaintenanceViewSet(Base):
 queryset=AssetMaintenance.objects.select_related("asset","vendor");serializer_class=AssetMaintenanceSerializer
 def perform_create(self,serializer):serializer.save(madrasa=self.get_madrasa(),recorded_by=self.request.user)
class VehicleViewSet(Base):queryset=Vehicle.objects.select_related("driver");serializer_class=VehicleSerializer;search_fields=["registration_number","name"]
class RouteViewSet(Base):queryset=TransportRoute.objects.select_related("vehicle","driver").prefetch_related("stops","student_assignments");serializer_class=RouteSerializer
class RouteStopViewSet(Base):queryset=RouteStop.objects.select_related("route");serializer_class=RouteStopSerializer
class TransportAssignmentViewSet(Base):queryset=StudentTransportAssignment.objects.select_related("student","route","stop");serializer_class=TransportAssignmentSerializer
class VehicleLogViewSet(Base):queryset=VehicleLog.objects.select_related("vehicle");serializer_class=VehicleLogSerializer
class MealPlanViewSet(Base):queryset=MealPlan.objects.prefetch_related("ingredients__item");serializer_class=MealPlanSerializer
class MealIngredientViewSet(Base):
 queryset=MealIngredient.objects.select_related("meal_plan","item");serializer_class=MealIngredientSerializer
 @action(detail=True,methods=["post"])
 @transaction.atomic
 def issue(self,request,pk=None):
  ing=self.get_object();qty=Decimal(str(request.data.get("quantity",ing.planned_quantity-ing.issued_quantity)));location_id=request.data.get("location");lots=StockLot.objects.select_for_update().filter(madrasa=self.get_madrasa(),item=ing.item,location_id=location_id,quantity__gt=0).order_by("expiry_date","received_at");remaining=qty
  for lot in lots:
   take=min(lot.quantity,remaining);lot.quantity-=take;lot.save(update_fields=["quantity"]);StockTransaction.objects.create(madrasa=self.get_madrasa(),item=ing.item,location=lot.location,lot=lot,transaction_type="issue",quantity=take,reference_type="meal_plan",reference_id=ing.meal_plan_id,created_by=request.user);remaining-=take
   if remaining<=0:break
  if remaining>0:raise serializers.ValidationError("Insufficient ingredient stock.")
  ing.issued_quantity+=qty;ing.save(update_fields=["issued_quantity"]);return Response(self.get_serializer(ing).data)
class OperationsDashboardViewSet(TenantScopedViewSetMixin,viewsets.ViewSet):
 queryset=InventoryItem.objects.none()
 def list(self,request):
  tenant=self.get_madrasa();items=InventoryItem.objects.filter(madrasa=tenant).prefetch_related("stock_lots");low=sum(1 for i in items if sum(l.quantity for l in i.stock_lots.all())<=i.reorder_level)
  return Response({"items":items.count(),"low_stock":low,"stock_value":StockLot.objects.filter(madrasa=tenant).aggregate(v=Sum(F("quantity")*F("unit_cost")))["v"] or 0,"open_orders":PurchaseOrder.objects.filter(madrasa=tenant,status__in=["draft","submitted","approved","part_received"]).count(),"assets":Asset.objects.filter(madrasa=tenant,status="active").count(),"vehicles":Vehicle.objects.filter(madrasa=tenant,status="active").count(),"transport_students":StudentTransportAssignment.objects.filter(madrasa=tenant,is_active=True).count(),"meals_today":MealPlan.objects.filter(madrasa=tenant,date=timezone.localdate()).count()})
