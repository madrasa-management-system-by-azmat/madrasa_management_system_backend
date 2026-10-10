from rest_framework import serializers
from .models import Asset, AssetMaintenance, InventoryItem, ItemCategory, MealIngredient, MealPlan, OperationsLocation, PurchaseOrder, PurchaseOrderLine, RouteStop, StockLot, StockTransaction, StudentTransportAssignment, TransportRoute, Vehicle, VehicleLog, Vendor

class LocationSerializer(serializers.ModelSerializer):
 class Meta:model=OperationsLocation;fields="__all__";read_only_fields=["madrasa"]
class ItemCategorySerializer(serializers.ModelSerializer):
 class Meta:model=ItemCategory;fields="__all__";read_only_fields=["madrasa"]
class ItemSerializer(serializers.ModelSerializer):
 stock=serializers.SerializerMethodField();category_name=serializers.CharField(source="category.name",read_only=True)
 class Meta:model=InventoryItem;fields="__all__";read_only_fields=["madrasa"]
 def get_stock(self,obj):return sum(l.quantity for l in obj.stock_lots.all())
class StockLotSerializer(serializers.ModelSerializer):
 item_name=serializers.CharField(source="item.name",read_only=True);location_name=serializers.CharField(source="location.name",read_only=True)
 class Meta:model=StockLot;fields="__all__";read_only_fields=["madrasa"]
class StockTransactionSerializer(serializers.ModelSerializer):
 class Meta:model=StockTransaction;fields="__all__";read_only_fields=["madrasa","created_by","created_at"]
class VendorSerializer(serializers.ModelSerializer):
 class Meta:model=Vendor;fields="__all__";read_only_fields=["madrasa"]
class PurchaseLineSerializer(serializers.ModelSerializer):
 item_name=serializers.CharField(source="item.name",read_only=True);total=serializers.DecimalField(max_digits=16,decimal_places=2,read_only=True)
 class Meta:model=PurchaseOrderLine;fields="__all__";read_only_fields=["madrasa"]
class PurchaseOrderSerializer(serializers.ModelSerializer):
 vendor_name=serializers.CharField(source="vendor.name",read_only=True);lines=PurchaseLineSerializer(many=True,read_only=True);total=serializers.SerializerMethodField()
 class Meta:model=PurchaseOrder;fields="__all__";read_only_fields=["madrasa","created_by","approved_by","approved_at","order_number"]
 def get_total(self,obj):return sum(line.total for line in obj.lines.all())
class AssetSerializer(serializers.ModelSerializer):
 location_name=serializers.CharField(source="location.name",read_only=True);custodian_name=serializers.CharField(source="custodian.full_name",read_only=True)
 class Meta:model=Asset;fields="__all__";read_only_fields=["madrasa"]
class AssetMaintenanceSerializer(serializers.ModelSerializer):
 class Meta:model=AssetMaintenance;fields="__all__";read_only_fields=["madrasa","recorded_by"]
class VehicleSerializer(serializers.ModelSerializer):
 driver_name=serializers.CharField(source="driver.full_name",read_only=True)
 class Meta:model=Vehicle;fields="__all__";read_only_fields=["madrasa"]
class RouteStopSerializer(serializers.ModelSerializer):
 class Meta:model=RouteStop;fields="__all__";read_only_fields=["madrasa"]
class RouteSerializer(serializers.ModelSerializer):
 vehicle_name=serializers.CharField(source="vehicle.name",read_only=True);stops=RouteStopSerializer(many=True,read_only=True);student_count=serializers.IntegerField(source="student_assignments.count",read_only=True)
 class Meta:model=TransportRoute;fields="__all__";read_only_fields=["madrasa"]
class TransportAssignmentSerializer(serializers.ModelSerializer):
 student_name=serializers.CharField(source="student.full_name",read_only=True);route_name=serializers.CharField(source="route.name",read_only=True);stop_name=serializers.CharField(source="stop.name",read_only=True)
 class Meta:model=StudentTransportAssignment;fields="__all__";read_only_fields=["madrasa"]
class VehicleLogSerializer(serializers.ModelSerializer):
 class Meta:model=VehicleLog;fields="__all__";read_only_fields=["madrasa"]
class MealIngredientSerializer(serializers.ModelSerializer):
 item_name=serializers.CharField(source="item.name",read_only=True)
 class Meta:model=MealIngredient;fields="__all__";read_only_fields=["madrasa"]
class MealPlanSerializer(serializers.ModelSerializer):
 ingredients=MealIngredientSerializer(many=True,read_only=True)
 class Meta:model=MealPlan;fields="__all__";read_only_fields=["madrasa"]
