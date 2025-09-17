from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

# Create your tests here.
from .models import (
    Brand,
    Category,
    Customer,
    Order,
    Payment,
    Product,
    Stock,
    Warehouse,
)
from .serializers import PaymentSerializer, StockSerializer


class BaseModelTestCase(TestCase):
    def setUp(self) -> None:
        self.brand = Brand.objects.create(name="Marca Test")
        self.category = Category.objects.create(name="Categoria Test")
        self.product = Product.objects.create(
            name="Producto Test",
            sku="SKU-001",
            price=Decimal("100.00"),
            brand=self.brand,
            category=self.category,
        )
        self.warehouse = Warehouse.objects.create(name="Central", city="Ciudad")
        self.customer = Customer.objects.create(
            full_name="Cliente de Prueba", email="cliente@example.com"
        )
        self.order = Order.objects.create(customer=self.customer)


class StockSerializerTests(BaseModelTestCase):
    def test_prevents_reserved_greater_than_quantity_on_create(self) -> None:
        serializer = StockSerializer(
            data={
                "product": str(self.product.id),
                "warehouse": str(self.warehouse.id),
                "qty": 5,
                "reserved": 6,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("reserved", serializer.errors)
        self.assertEqual(
            serializer.errors["reserved"][0],
            "La cantidad reservada no puede exceder la cantidad total disponible",
        )

    def test_prevents_reserved_greater_than_quantity_on_update(self) -> None:
        stock = Stock.objects.create(
            product=self.product,
            warehouse=self.warehouse,
            qty=10,
            reserved=2,
        )

        serializer = StockSerializer(
            instance=stock,
            data={
                "product": str(self.product.id),
                "warehouse": str(self.warehouse.id),
                "qty": 5,
                "reserved": 6,
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("reserved", serializer.errors)

    def test_prevents_duplicate_stock_per_product_and_warehouse(self) -> None:
        Stock.objects.create(
            product=self.product,
            warehouse=self.warehouse,
            qty=5,
            reserved=1,
        )

        serializer = StockSerializer(
            data={
                "product": str(self.product.id),
                "warehouse": str(self.warehouse.id),
                "qty": 5,
                "reserved": 0,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)
        self.assertEqual(
            serializer.errors["non_field_errors"][0],
            "Ya existe stock para este producto en esta bodega",
        )

    def test_model_clean_validates_reserved_quantity(self) -> None:
        stock = Stock(
            product=self.product,
            warehouse=self.warehouse,
            qty=3,
            reserved=4,
        )

        with self.assertRaises(ValidationError) as exc:
            stock.full_clean()

        self.assertIn("reserved", exc.exception.error_dict)


class PaymentSerializerTests(BaseModelTestCase):
    def test_prevents_duplicate_payments_per_order(self) -> None:
        Payment.objects.create(
            order=self.order,
            method=Payment.Method.CARD,
            amount=Decimal("100.00"),
            status=Payment.Status.PENDING,
        )

        serializer = PaymentSerializer(
            data={
                "order": str(self.order.id),
                "method": Payment.Method.TRANSFER,
                "amount": Decimal("100.00"),
                "status": Payment.Status.PENDING,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("order", serializer.errors)
        self.assertEqual(
            serializer.errors["order"][0], "La orden ya tiene un pago registrado"
        )

    def test_allows_updating_existing_payment(self) -> None:
        payment = Payment.objects.create(
            order=self.order,
            method=Payment.Method.CARD,
            amount=Decimal("100.00"),
            status=Payment.Status.PENDING,
        )

        serializer = PaymentSerializer(
            instance=payment,
            data={
                "order": str(self.order.id),
                "method": Payment.Method.CARD,
                "amount": Decimal("150.00"),
                "status": Payment.Status.CONFIRMED,
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()

        self.assertEqual(updated.amount, Decimal("150.00"))
        self.assertEqual(updated.status, Payment.Status.CONFIRMED)