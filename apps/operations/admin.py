from django.contrib import admin
from .models import *
for model in [OperationsLocation,ItemCategory,InventoryItem,StockLot,StockTransaction,Vendor,PurchaseOrder,PurchaseOrderLine,Asset,AssetMaintenance,Vehicle,TransportRoute,RouteStop,StudentTransportAssignment,VehicleLog,MealPlan,MealIngredient]:admin.site.register(model)
