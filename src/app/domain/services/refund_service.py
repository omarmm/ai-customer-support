from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.app.domain.exceptions import (
    InvalidRefundAmountError,
    OrderNotFoundError,
    RefundAmountExceedsOrderError,
    RefundWindowExpiredError,
)
from src.app.domain.models.order import Order
from src.app.domain.models.refund import Refund, RefundStatus


class RefundService:
    def __init__(
        self,
        session: Session,
        refund_window_days: int = 30,
    ) -> None:
        self.session = session
        self.refund_window_days = refund_window_days

    def request_refund(
        self,
        order_id: int,
        amount: Decimal,
    ) -> Refund:
        """
        Validate and create a refund request atomically.

        If the caller already owns a transaction, the service
        participates in that transaction.

        Otherwise, the service creates and owns the transaction.
        """

        if self.session.in_transaction():
            return self._request_refund(order_id, amount)

        with self.session.begin():
            return self._request_refund(order_id, amount)

    def _request_refund(
        self,
        order_id: int,
        amount: Decimal,
    ) -> Refund:
        order = self._get_locked_order(order_id)

        self._validate_amount(amount)
        self._validate_refund_window(order)
        self._validate_refund_amount(order, amount)

        refund = Refund(
            order_id=order.id,
            amount=amount,
            status=RefundStatus.REQUESTED,
        )

        self.session.add(refund)
        self.session.flush()

        return refund

    def _get_locked_order(self, order_id: int) -> Order:
        statement = (
            select(Order)
            .where(Order.id == order_id)
            .with_for_update()
        )

        order = self.session.execute(statement).scalar_one_or_none()

        if order is None:
            raise OrderNotFoundError(
                f"Order {order_id} was not found."
            )

        return order

    def _validate_amount(self, amount: Decimal) -> None:
        if amount <= Decimal("0"):
            raise InvalidRefundAmountError(
                "Refund amount must be greater than zero."
            )

    def _validate_refund_window(self, order: Order) -> None:
        now = datetime.now(timezone.utc)

        order_created_at = order.created_at

        if order_created_at.tzinfo is None:
            order_created_at = order_created_at.replace(
                tzinfo=timezone.utc
            )

        deadline = order_created_at + timedelta(
            days=self.refund_window_days
        )

        if now > deadline:
            raise RefundWindowExpiredError(
                f"Order {order.id} is outside the "
                f"{self.refund_window_days}-day refund window."
            )

    def _validate_refund_amount(
        self,
        order: Order,
        requested_amount: Decimal,
    ) -> None:
        if requested_amount > order.amount:
            raise RefundAmountExceedsOrderError(
                "Requested refund exceeds order amount."
            )

        refunded_amount = self.session.execute(
            select(
                func.coalesce(
                    func.sum(Refund.amount),
                    Decimal("0.00"),
                )
            )
            .where(
                Refund.order_id == order.id,
                Refund.status != RefundStatus.REJECTED,
            )
        ).scalar_one()

        if refunded_amount + requested_amount > order.amount:
            raise RefundAmountExceedsOrderError(
                "Cumulative refunds exceed order amount."
            )
