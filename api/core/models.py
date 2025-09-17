import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Index, Q

# Create your models here.

class Brand(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    brand = models.ForeignKey(
        "Brand",
        on_delete=models.PROTECT,
        related_name="products",
    )
    category = models.ForeignKey(
        "Category",
        on_delete=models.PROTECT,
        related_name="products",
    )

    class Meta:
        indexes = [Index(fields=["sku"], name="product_sku_idx")]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"


class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} - {self.city}"


class Stock(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    qty = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    reserved = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    updated_at = models.DateTimeField(auto_now=True)
    product = models.ForeignKey(
        "Product",
        on_delete=models.CASCADE,
        related_name="stocks",
    )
    warehouse = models.ForeignKey(
        "Warehouse",
        on_delete=models.CASCADE,
        related_name="stocks",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "warehouse"],
                name="unique_stock_product_warehouse",
            ),
            models.CheckConstraint(
                check=Q(reserved__lte=F("qty")),
                name="stock_reserved_lte_qty",
            ),
        ]
        indexes = [
            Index(
                fields=["product", "warehouse"],
                name="stock_product_warehouse_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.reserved > self.qty:
            raise ValidationError({"reserved": "Reserved quantity cannot exceed total quantity."})

    def __str__(self) -> str:
        return f"{self.product} @ {self.warehouse}"


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}>"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELED = "CANCELED", "Canceled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.PROTECT,
        related_name="orders",
    )

    class Meta:
        indexes = [
            Index(fields=["status", "created_at"], name="order_status_created_at_idx"),
        ]

    def __str__(self) -> str:
        return f"Order {self.id} ({self.status})"


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    qty = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    order = models.ForeignKey(
        "Order",
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    def __str__(self) -> str:
        return f"{self.qty} x {self.product}"


class Payment(models.Model):
    class Method(models.TextChoices):
        CARD = "CARD", "Card"
        TRANSFER = "TRANSFER", "Transfer"
        COD = "COD", "Cash on Delivery"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    method = models.CharField(max_length=20, choices=Method.choices)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.OneToOneField(
        "Order",
        on_delete=models.CASCADE,
        related_name="payment",
        null=True,
        blank=True,
    )

    class Meta:
        indexes = [
            Index(fields=["status", "created_at"], name="payment_status_created_at_idx"),
        ]

    def __str__(self) -> str:
        if self.order:
            return f"Payment for Order {self.order_id} - {self.status}"
        return f"Payment {self.id} - {self.status}"