import pytest
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from src.app.domain.models.customer import Customer
from src.app.domain.models.order import Order, OrderStatus
from src.app.domain.models.refund import Refund, RefundStatus
from src.app.infrastructure.database.session import SessionLocal


def test_customer_email_must_be_unique():
    session = SessionLocal()

    try:
        customer1 = Customer(
            name="Customer One",
            email="unique@example.com",
        )

        customer2 = Customer(
            name="Customer Two",
            email="unique@example.com",
        )

        session.add_all([customer1, customer2])

        with pytest.raises(IntegrityError):
            session.commit()

    finally:
        session.rollback()
        session.close()


def test_order_must_reference_existing_customer():
    session = SessionLocal()

    try:
        order = Order(
            customer_id=999999,
            amount=Decimal("100.00"),
            status=OrderStatus.PENDING,
        )

        session.add(order)

        with pytest.raises(IntegrityError):
            session.commit()

    finally:
        session.rollback()
        session.close()


def test_refund_must_reference_existing_order():
    session = SessionLocal()

    try:
        refund = Refund(
            order_id=999999,
            amount=Decimal("50.00"),
            status=RefundStatus.REQUESTED,
        )

        session.add(refund)

        with pytest.raises(IntegrityError):
            session.commit()

    finally:
        session.rollback()
        session.close()


def test_customer_cannot_be_deleted_while_orders_exist():
    session = SessionLocal()

    try:
        customer = Customer(
            name="Delete Test Customer",
            email="delete-customer@example.com",
        )

        session.add(customer)
        session.commit()

        order = Order(
            customer_id=customer.id,
            amount=Decimal("100.00"),
            status=OrderStatus.PENDING,
        )

        session.add(order)
        session.commit()

        session.delete(customer)

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()

        session.delete(order)
        session.delete(customer)
        session.commit()

    finally:
        session.close()


def test_order_cannot_be_deleted_while_refunds_exist():
    session = SessionLocal()

    try:
        customer = Customer(
            name="Refund Delete Test Customer",
            email="delete-order@example.com",
        )

        session.add(customer)
        session.commit()

        order = Order(
            customer_id=customer.id,
            amount=Decimal("100.00"),
            status=OrderStatus.PAID,
        )

        session.add(order)
        session.commit()

        refund = Refund(
            order_id=order.id,
            amount=Decimal("50.00"),
            status=RefundStatus.REQUESTED,
        )

        session.add(refund)
        session.commit()

        session.delete(order)

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()

        session.delete(refund)
        session.delete(order)
        session.delete(customer)
        session.commit()

    finally:
        session.close()