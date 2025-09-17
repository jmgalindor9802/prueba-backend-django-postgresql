from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet

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
from .serializers import (
    BrandSerializer,
    CategorySerializer,
    CustomerSerializer,
    OrderItemSerializer,
    OrderSerializer,
    PaymentSerializer,
    ProductSerializer,
    StockSerializer,
    WarehouseSerializer,
)


class BrandViewSet(ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [AllowAny]
    filterset_fields = ["id", "name", "is_active", "created_at"]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ("name",)

class CategoryViewSet(ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    filterset_fields = ["id", "name", "is_active", "created_at"]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ("name",)

class ProductViewSet(ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    filterset_fields = [
        "id",
        "name",
        "sku",
        "brand",
        "category",
        "is_active",
        "price",
        "created_at",
    ]
    search_fields = ["name", "sku", "brand__name", "category__name"]
    ordering_fields = ["name", "price", "created_at", "sku"]
    ordering = ("-created_at",)

    def get_queryset(self):
        queryset = super().get_queryset().select_related("brand", "category")
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("stocks")
        return queryset


class WarehouseViewSet(ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [AllowAny]
    filterset_fields = ["id", "name", "city", "created_at"]
    search_fields = ["name", "city"]
    ordering_fields = ["name", "city", "created_at"]
    ordering = ("name",)

class StockViewSet(ModelViewSet):
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    permission_classes = [AllowAny]
    filterset_fields = [
        "id",
        "product",
        "warehouse",
        "qty",
        "reserved",
        "updated_at",
    ]
    search_fields = ["product__name", "product__sku", "warehouse__name", "warehouse__city"]
    ordering_fields = ["qty", "reserved", "updated_at"]
    ordering = ("-updated_at",)

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "product",
                "product__brand",
                "product__category",
                "warehouse",
            )
        )


class CustomerViewSet(ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [AllowAny]
    filterset_fields = ["id", "full_name", "email", "created_at"]
    search_fields = ["full_name", "email"]
    ordering_fields = ["full_name", "email", "created_at"]
    ordering = ("full_name",)

class OrderViewSet(ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [AllowAny]
    filterset_fields = ["id", "status", "customer", "created_at"]
    search_fields = ["status", "customer__full_name", "customer__email"]
    ordering_fields = ["created_at", "status"]
    ordering = ("-created_at",)

    def get_queryset(self):
        queryset = super().get_queryset().select_related("customer", "payment")
        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                "items",
                "items__product",
                "items__product__brand",
                "items__product__category",
            )
        return queryset


class OrderItemViewSet(ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [AllowAny]
    filterset_fields = ["id", "order", "product", "qty", "unit_price"]
    search_fields = ["product__name", "product__sku", "order__customer__full_name"]
    ordering_fields = ["qty", "unit_price"]
    ordering = ("-unit_price",)

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "order",
                "order__customer",
                "product",
                "product__brand",
                "product__category",
            )
        )


class PaymentViewSet(ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [AllowAny]
    filterset_fields = ["id", "method", "status", "order", "amount", "created_at"]
    search_fields = ["method", "status", "order__customer__full_name", "order__customer__email"]
    ordering_fields = ["amount", "created_at", "status"]
    ordering = ("-created_at",)

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("order", "order__customer")
        )