# Domain Business Rules

## Refund Authorization

Refund authorization is a deterministic backend responsibility.

Neither the LLM nor an Agent may approve, reject, or override
a refund business decision.

## Rules

### R1 — Backend Authorization

All refund requests must be validated by backend business rules.

### R2 — Refund Amount

The requested refund amount must be greater than zero.

The requested refund amount must not exceed the order amount.

### R3 — Cumulative Refunds

The cumulative amount of active refunds plus the requested refund
must not exceed the order amount.

Rejected refunds do not count toward the refundable amount.

### R4 — Refund Window

An order is refundable only within the configured refund window.

The current default policy is 30 days from the order creation time.

### R5 — Cross-Entity Business Rules

Rules that require both Order and Refund data belong to
RefundService / Domain Service.

### R6 — Concurrency

Refund authorization and creation must happen atomically.

The relevant Order must be locked during the transaction so that
concurrent refund requests cannot both authorize the same remaining
refundable amount.

PostgreSQL row-level locking (`SELECT ... FOR UPDATE`) is used.

### R7 — AI Boundary

The LLM/Agent may understand customer intent and request a refund
operation through a backend tool.

The LLM/Agent cannot bypass or override these business rules.
