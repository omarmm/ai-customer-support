# Database Specification

## Purpose

Define the transactional data model and persistence boundaries for the AI Customer Support Backend.

## Database

PostgreSQL is the system of record for transactional and business data.

The application must not use the vector database as a source of truth for transactional state.

## Entities

### Customer

Represents a customer who owns orders.

Fields:

- `id`
- `email`
- `name`
- `created_at`

Requirements:

- `id` is the primary key.
- `email` must be unique.
- `created_at` is required.

### Order

Represents a customer purchase.

Fields:

- `id`
- `customer_id`
- `status`
- `total_amount`
- `currency`
- `created_at`

Requirements:

- `id` is the primary key.
- `customer_id` references `Customer`.
- An order must belong to exactly one customer.
- `total_amount` must be non-negative.
- `currency` is required.
- `status` must use a controlled set of values.

Initial order statuses:

- `pending`
- `confirmed`
- `shipped`
- `delivered`
- `cancelled`

### Refund

Represents a refund associated with an order.

Fields:

- `id`
- `order_id`
- `amount`
- `status`
- `created_at`

Requirements:

- `id` is the primary key.
- `order_id` references `Order`.
- `amount` must be positive.
- A refund cannot exceed the refundable amount of the order.
- Refund state changes must be controlled by backend business rules.

Initial refund statuses:

- `pending`
- `completed`
- `failed`

## Relationships

```text
Customer 1 ──────── N Order
Order    1 ──────── N Refund