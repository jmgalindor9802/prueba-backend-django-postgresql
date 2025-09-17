"""Serializadores para los modelos principales"""
from typing import Any, Dict

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from .models import (
    Brand,
    Category,
    Customer,
    Order,
    OrderItem,
    Payment,
    Product,
    Stock,
    Warehouse,
)


class BaseModelSerializer(serializers.ModelSerializer):
    """Configura campos comunes como solo lectura si están presente"""

    read_only_common_fields = ("id", "created_at", "updated_at")

    def get_fields(self) -> Dict[str, serializers.Field]:
        fields = super().get_fields()
        for field_name in self.read_only_common_fields:
            field = fields.get(field_name)
            if field is not None:
                field.read_only = True
        return fields


class BrandSerializer(BaseModelSerializer):
    class Meta:
        model = Brand
        fields = "__all__"
        read_only_fields = ("id", "created_at")


class CategorySerializer(BaseModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"
        read_only_fields = ("id", "created_at")


class ProductSerializer(BaseModelSerializer):
    brand = serializers.PrimaryKeyRelatedField(queryset=Brand.objects.all())
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())

    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = ("id", "created_at")


class WarehouseSerializer(BaseModelSerializer):
    class Meta:
        model = Warehouse
        fields = "__all__"
        read_only_fields = ("id", "created_at")


class StockSerializer(BaseModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())

    class Meta:
        model = Stock
        fields = "__all__"
        read_only_fields = ("id", "updated_at")
        validators = [
            UniqueTogetherValidator(
                queryset=Stock.objects.all(),
                fields=("product", "warehouse"),
                message="Ya existe stock para este producto en esta bodega",
            )
        ]

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        instance = getattr(self, "instance", None)
        qty = attrs.get("qty", getattr(instance, "qty", None))
        reserved = attrs.get("reserved", getattr(instance, "reserved", None))

        if qty is not None and reserved is not None and reserved > qty:
            raise serializers.ValidationError(
                {"reserved": "La cantidad reservada no puede exceder la cantidad total disponible"}
            )

        return super().validate(attrs)


class CustomerSerializer(BaseModelSerializer):
    class Meta:
        model = Customer
        fields = "__all__"
        read_only_fields = ("id", "created_at")


class OrderSerializer(BaseModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())

    class Meta:
        model = Order
        fields = "__all__"
        read_only_fields = ("id", "created_at")


class OrderItemSerializer(BaseModelSerializer):
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = OrderItem
        fields = "__all__"
        read_only_fields = ("id",)


class PaymentSerializer(BaseModelSerializer):
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ("id", "created_at")

    def validate_order(self, order: Order | None) -> Order | None:
        if order is None:
            return order

        instance = getattr(self, "instance", None)
        if instance is not None and instance.order_id == order.id:
            return order

        try:
            existing_payment = order.payment
        except Payment.DoesNotExist:
            existing_payment = None

        if existing_payment is not None:
            raise serializers.ValidationError("La orden ya tiene un pago registrado")

        return order