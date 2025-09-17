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

from .mixins import RelatedQueryMixin


class BaseViewSet(RelatedQueryMixin, ModelViewSet):
    """ViewSet base que incluye la lógica de ``get_related``."""


class BrandViewSet(BaseViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [AllowAny]
    related_allowed_joins = (
        "products",
        "products.category",
        "products.order_items",
        "products.order_items.order",
        "products.stocks",
        "products.stocks.warehouse",
    )
    filterset_fields = ["id", "name", "is_active", "created_at"]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ("name",)


class CategoryViewSet(BaseViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    related_allowed_joins = (
        "products",
        "products.brand",
        "products.order_items",
        "products.order_items.order",
        "products.stocks",
        "products.stocks.warehouse",
    )
    filterset_fields = ["id", "name", "is_active", "created_at"]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ("name",)


class ProductViewSet(BaseViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    related_allowed_joins = (
        "brand",
        "category",
        "stocks",
        "stocks.warehouse",
        "order_items",
        "order_items.order",
        "order_items.order.customer",
        "order_items.order.payment",
    )
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


class WarehouseViewSet(BaseViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [AllowAny]
    related_allowed_joins = (
        "stocks",
        "stocks.product",
        "stocks.product.brand",
        "stocks.product.category",
    )
    filterset_fields = ["id", "name", "city", "created_at"]
    search_fields = ["name", "city"]
    ordering_fields = ["name", "city", "created_at"]
    ordering = ("name",)


class StockViewSet(BaseViewSet):
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    permission_classes = [AllowAny]
    related_allowed_joins = (
        "product",
        "product.brand",
        "product.category",
        "warehouse",
    )
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


class CustomerViewSet(BaseViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [AllowAny]
    related_allowed_joins = (
        "orders",
        "orders.payment",
        "orders.items",
        "orders.items.product",
    )
    filterset_fields = ["id", "full_name", "email", "created_at"]
    search_fields = ["full_name", "email"]
    ordering_fields = ["full_name", "email", "created_at"]
    ordering = ("full_name",)


class OrderViewSet(BaseViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [AllowAny]
    related_allowed_joins = (
        "customer",
        "payment",
        "items",
        "items.product",
        "items.product.brand",
        "items.product.category",
    )
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


class OrderItemViewSet(BaseViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [AllowAny]
    related_allowed_joins = (
        "order",
        "order.customer",
        "order.payment",
        "product",
        "product.brand",
        "product.category",
    )
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


class PaymentViewSet(BaseViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [AllowAny]
    related_allowed_joins = (
        "order",
        "order.customer",
        "order.items",
        "order.items.product",
    )
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
