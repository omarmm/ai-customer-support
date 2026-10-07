class DomainError(Exception):
    """Base exception for domain/business rule violations."""


class OrderNotFoundError(DomainError):
    pass


class InvalidRefundAmountError(DomainError):
    pass


class RefundAmountExceedsOrderError(DomainError):
    pass


class RefundWindowExpiredError(DomainError):
    pass
