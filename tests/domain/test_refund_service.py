from uuid import uuid4
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.app.domain.exceptions import (
    InvalidRefundAmountError,
    OrderNotFoundError,
    RefundAmountExceedsOrderError,
    RefundWindowExpiredError,
)
from src.app.domain.models.customer import Customer
from src.app.domain.models.order import Order, OrderStatus
from src.app.domain.models.refund import Refund, RefundStatus
from src.app.domain.services.refund_service import RefundService
from src.app.infrastructure.database.session import SessionLocal


def create_customer(session):
    customer = Customer(
        name="Refund Test Customer",
        email=f"refund-test-{uuid4()}@example.com",
    )

    session.add(customer)
    session.commit()

    return customer


def create_order(
    session,
    customer_id,
    amount=Decimal("100.00"),
    created_at=None,
):
    order = Order(
        customer_id=customer_id,
        amount=amount,
        status=OrderStatus.PAID,
        created_at=created_at or datetime.now(timezone.utc),
    )

    session.add(order)
    session.commit()

    return order


def test_valid_refund_request_is_created():
    session = SessionLocal()

    try:
        customer = create_customer(session)
        order = create_order(session, customer.id)

        refund = RefundService(session).request_refund(
            order_id=order.id,
            amount=Decimal("40.00"),
        )

        assert refund.id is not None
        assert refund.order_id == order.id
        assert refund.amount == Decimal("40.00")
        assert refund.status == RefundStatus.REQUESTED

    finally:
        session.close()


def test_refund_cannot_exceed_order_amount():
    session = SessionLocal()

    try:
        customer = create_customer(session)
        order = create_order(session, customer.id)

        with pytest.raises(RefundAmountExceedsOrderError):
            RefundService(session).request_refund(
                order_id=order.id,
                amount=Decimal("120.00"),
            )

    finally:
        session.close()


def test_cumulative_refunds_cannot_exceed_order_amount():
    session = SessionLocal()

    try:
        customer = create_customer(session)
        order = create_order(session, customer.id)

        existing_refund = Refund(
            order_id=order.id,
            amount=Decimal("60.00"),
            status=RefundStatus.PROCESSED,
        )

        session.add(existing_refund)
        session.commit()

        with pytest.raises(RefundAmountExceedsOrderError):
            RefundService(session).request_refund(
                order_id=order.id,
                amount=Decimal("50.00"),
            )

    finally:
        session.close()


def test_rejected_refunds_do_not_count():
    session = SessionLocal()

    try:
        customer = create_customer(session)
        order = create_order(session, customer.id)

        rejected_refund = Refund(
            order_id=order.id,
            amount=Decimal("90.00"),
            status=RefundStatus.REJECTED,
        )

        session.add(rejected_refund)
        session.commit()

        refund = RefundService(session).request_refund(
            order_id=order.id,
            amount=Decimal("50.00"),
        )

        assert refund.amount == Decimal("50.00")

    finally:
        session.close()


def test_refund_window_expired():
    session = SessionLocal()

    try:
        customer = create_customer(session)

        created_at = datetime.now(timezone.utc) - timedelta(days=31)

        order = create_order(
            session,
            customer.id,
            created_at=created_at,
        )

        with pytest.raises(RefundWindowExpiredError):
            RefundService(session).request_refund(
                order_id=order.id,
                amount=Decimal("20.00"),
            )

    finally:
        session.close()


def test_refund_amount_must_be_positive():
    session = SessionLocal()

    try:
        customer = create_customer(session)
        order = create_order(session, customer.id)

        with pytest.raises(InvalidRefundAmountError):
            RefundService(session).request_refund(
                order_id=order.id,
                amount=Decimal("0.00"),
            )

    finally:
        session.close()


def test_order_must_exist():
    session = SessionLocal()

    try:
        with pytest.raises(OrderNotFoundError):
            RefundService(session).request_refund(
                order_id=999999,
                amount=Decimal("20.00"),
            )

    finally:
        session.close()
