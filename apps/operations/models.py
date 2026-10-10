from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class OperationsLocation(models.Model):
    class LocationType(models.TextChoices):
        STORE = "store", "Store"
        KITCHEN = "kitchen", "Kitchen"
        HOSTEL = "hostel", "Hostel"
        WORKSHOP = "workshop", "Workshop"
        OFFICE = "office", "Office"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="operations_locations")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    location_type = models.CharField(max_length=20, choices=LocationType.choices)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="managed_operations_locations")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["location_type", "name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "code"], name="unique_operations_location_code")]


class ItemCategory(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="item_categories")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, blank=True, null=True, related_name="children")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["madrasa", "code"], name="unique_item_category_code")]


class InventoryItem(models.Model):
    class ItemType(models.TextChoices):
        CONSUMABLE = "consumable", "Consumable"
        DURABLE = "durable", "Durable"
        CAPITAL = "capital_asset", "Capital asset"
        FUEL = "fuel", "Fuel"
        INGREDIENT = "ingredient", "Ingredient"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="inventory_items")
    sku = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(ItemCategory, on_delete=models.PROTECT, related_name="items")
    item_type = models.CharField(max_length=30, choices=ItemType.choices)
    unit = models.CharField(max_length=30, default="unit")
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    track_expiry = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "sku"], name="unique_inventory_sku")]


class StockLot(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="stock_lots")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="stock_lots")
    location = models.ForeignKey(OperationsLocation, on_delete=models.PROTECT, related_name="stock_lots")
    lot_number = models.CharField(max_length=80, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expiry_date = models.DateField(blank=True, null=True)
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["expiry_date", "received_at"]
        constraints = [models.UniqueConstraint(fields=["item", "location", "lot_number"], name="unique_item_location_lot")]


class StockTransaction(models.Model):
    class TransactionType(models.TextChoices):
        RECEIPT = "receipt", "Receipt"
        ISSUE = "issue", "Issue"
        ADJUSTMENT = "adjustment", "Adjustment"
        TRANSFER_IN = "transfer_in", "Transfer in"
        TRANSFER_OUT = "transfer_out", "Transfer out"
        WASTAGE = "wastage", "Wastage"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="stock_transactions")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="stock_transactions")
    location = models.ForeignKey(OperationsLocation, on_delete=models.PROTECT, related_name="stock_transactions")
    lot = models.ForeignKey(StockLot, on_delete=models.PROTECT, blank=True, null=True, related_name="transactions")
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveBigIntegerField(blank=True, null=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="stock_transactions_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Vendor(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="vendors")
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    tax_number = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "name"], name="unique_vendor_name")]


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        PART_RECEIVED = "part_received", "Part received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="purchase_orders")
    order_number = models.CharField(max_length=60)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="purchase_orders")
    location = models.ForeignKey(OperationsLocation, on_delete=models.PROTECT, related_name="purchase_orders")
    order_date = models.DateField(default=timezone.localdate)
    expected_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    fund = models.ForeignKey("finance.Fund", on_delete=models.PROTECT, blank=True, null=True, related_name="purchase_orders")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="purchase_orders_created")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="purchase_orders_approved")
    approved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-order_date", "-id"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "order_number"], name="unique_purchase_order_number")]


class PurchaseOrderLine(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="purchase_order_lines")
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="purchase_lines")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=[MinValueValidator(0.001)])
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    received_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    @property
    def total(self):
        return self.quantity * self.unit_price


class Asset(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        IN_REPAIR = "in_repair", "In repair"
        RETIRED = "retired", "Retired"
        DISPOSED = "disposed", "Disposed"
        LOST = "lost", "Lost"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="assets")
    asset_number = models.CharField(max_length=60)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, blank=True, null=True, related_name="assets")
    location = models.ForeignKey(OperationsLocation, on_delete=models.PROTECT, related_name="assets")
    custodian = models.ForeignKey("staff.Staff", on_delete=models.SET_NULL, blank=True, null=True, related_name="custodied_assets")
    acquisition_date = models.DateField()
    acquisition_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    useful_life_months = models.PositiveIntegerField(default=60)
    serial_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["asset_number"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "asset_number"], name="unique_asset_number")]


class AssetMaintenance(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="asset_maintenance")
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="maintenance_records")
    maintenance_date = models.DateField(default=timezone.localdate)
    maintenance_type = models.CharField(max_length=100)
    description = models.TextField()
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    next_due_date = models.DateField(blank=True, null=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, blank=True, null=True, related_name="asset_maintenance")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="asset_maintenance_recorded")


class Vehicle(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="vehicles")
    registration_number = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    vehicle_type = models.CharField(max_length=50)
    capacity = models.PositiveSmallIntegerField(default=1)
    driver = models.ForeignKey("staff.Staff", on_delete=models.SET_NULL, blank=True, null=True, related_name="driven_vehicles")
    status = models.CharField(max_length=20, choices=[("active", "Active"), ("maintenance", "Maintenance"), ("inactive", "Inactive")], default="active")
    insurance_expiry = models.DateField(blank=True, null=True)
    fitness_expiry = models.DateField(blank=True, null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["madrasa", "registration_number"], name="unique_vehicle_registration")]


class TransportRoute(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="transport_routes")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, blank=True, null=True, related_name="routes")
    driver = models.ForeignKey("staff.Staff", on_delete=models.SET_NULL, blank=True, null=True, related_name="transport_routes")
    monthly_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["madrasa", "code"], name="unique_transport_route_code")]


class RouteStop(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="route_stops")
    route = models.ForeignKey(TransportRoute, on_delete=models.CASCADE, related_name="stops")
    sequence = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=150)
    pickup_time = models.TimeField(blank=True, null=True)
    drop_time = models.TimeField(blank=True, null=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [models.UniqueConstraint(fields=["route", "sequence"], name="unique_route_stop_sequence")]


class StudentTransportAssignment(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="student_transport_assignments")
    student = models.OneToOneField("students.Student", on_delete=models.PROTECT, related_name="transport_assignment")
    route = models.ForeignKey(TransportRoute, on_delete=models.PROTECT, related_name="student_assignments")
    stop = models.ForeignKey(RouteStop, on_delete=models.PROTECT, related_name="student_assignments")
    starts_on = models.DateField(default=timezone.localdate)
    ends_on = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)


class VehicleLog(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="vehicle_logs")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="logs")
    date = models.DateField(default=timezone.localdate)
    log_type = models.CharField(max_length=20, choices=[("trip", "Trip"), ("fuel", "Fuel"), ("maintenance", "Maintenance")])
    odometer = models.PositiveIntegerField(default=0)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)


class MealPlan(models.Model):
    class MealType(models.TextChoices):
        BREAKFAST = "breakfast", "Breakfast"
        LUNCH = "lunch", "Lunch"
        DINNER = "dinner", "Dinner"
        SNACK = "snack", "Snack"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="meal_plans")
    date = models.DateField()
    meal_type = models.CharField(max_length=20, choices=MealType.choices)
    menu = models.CharField(max_length=300)
    planned_servings = models.PositiveIntegerField(default=0)
    actual_servings = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["date", "meal_type"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "date", "meal_type"], name="unique_meal_plan")]


class MealIngredient(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="meal_ingredients")
    meal_plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE, related_name="ingredients")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="meal_ingredients")
    planned_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    issued_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    wasted_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["meal_plan", "item"], name="unique_meal_ingredient")]
