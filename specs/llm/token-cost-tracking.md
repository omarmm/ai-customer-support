# LLM Token & Cost Tracking Specification

**Status:** Approved
**Feature:** Token and Cost Tracking
**Phase:** LLM Service (Phase 3)

**Related task:**
- **T254** — token/cost accounting implementation.

This document defines token accounting and cost calculation for the LLM Service.
It builds on and must not contradict `specs/llm/llm-service.md` (§7, §11, §12),
`specs/llm/error-handling.md` (§2, §8, §9), and
`specs/system/configuration.md`.

**Decision log:**
- `LLMUsage` remains the provider-sourced token accounting value object; its
  shape is unchanged.
- A separate `LLMCost` value object carries derived cost, exposed through an
  additive optional `LLMResponse.cost` field.
- Provider adapters report raw usage only; they never calculate cost.
- Missing pricing/usage is represented explicitly as `None` and is never
  silently treated as zero. An explicitly configured zero price is a valid,
  known cost (`Decimal("0")`).
- A deterministic `cost_status` value is exposed on `response.metadata`.

## 1. Purpose

Capture provider-sourced token usage and derived cost at the LLM Service
boundary, provider-neutrally and testably, so LLM spend is observable without
leaking provider specifics into application or domain code.

T254 is accounting and observability only; it makes no business decisions.

## 2. Scope

In scope:

- Normalized token-usage contract (facts sourced from providers; never
  fabricated).
- A pricing table externalized through configuration.
- A pure, injectable `CostCalculator` applied at the LLM Service boundary.
- Per-request usage/cost plus a deterministic pricing status exposed on the
  normalized response.
- Explicit representation of unavailable cost, distinct from a configured zero
  price.
- Validation with clear failure for malformed pricing configuration.
- Unit tests with no network or live provider.

Out of scope:

- Aggregate/cumulative accounting, dashboards, metrics backends (Phase 8
  "Cost monitoring").
- Budgets, quotas, spend authorization or enforcement (backend/domain
  authority).
- Billing-grade guarantees, currency conversion, multi-currency mixing.
- Token usage of failed/retried attempts that return no usage (see §6).
- Runtime price fetching; prices are operator-supplied.
- Provider adapters computing cost (they report usage only).
- Introducing a DI container or composition root where none exists (§5.5).

## 3. Token Usage Contract

`LLMUsage(input_tokens: int | None, output_tokens: int | None,
total_tokens: int | None)` remains **provider-sourced** and unchanged in shape.

Normalization rules (explicit):

1. Provider adapters own extraction (for example Ollama `prompt_eval_count` /
   `eval_count`) and must never fabricate token counts.
2. A **provider-reported** `total_tokens` is authoritative and preserved as-is.
3. When no provider total is reported, `total_tokens` is derived **only if
   both** `input_tokens` and `output_tokens` are known:
   `total_tokens = input + output`.
4. If only one of input/output is known and no provider total exists,
   `total_tokens = None`. Unknown is `None`; `0` is never a substitute for
   unknown.
5. `0` is a valid known value and is distinct from unknown.
6. Unknown usage never fails a successful generation.

Compliance note: the Ollama adapter previously derived a total when *either*
component was present (`(input or 0) + (output or 0)`). T254 tightens this to
the both-known rule (§3.3). No existing test asserted the partial case.

## 4. Cost Model

### 4.1 Value object

`LLMCost(input_cost: Decimal | None, output_cost: Decimal | None,
total_cost: Decimal | None, currency: str)`.

### 4.2 Pricing

- Pricing is keyed by `model`, priced **per one million tokens**, with a single
  configured currency.
- Prices are configuration, never hard-coded in logic.
- An **explicitly configured zero price** yields `Decimal("0")` — a known cost,
  not unavailable.
- **Missing pricing** (empty table or model absent) yields
  `response.cost is None` — unavailable, never zero. Empty or absent pricing is
  valid; no placeholder prices are introduced.

### 4.3 Partial-cost semantics (exact)

1. `input_cost` is computed if and only if the model's input price is configured
   and `input_tokens` is known.
2. `output_cost` is computed if and only if the model's output price is
   configured and `output_tokens` is known.
3. `total_cost` is set **only when both `input_cost` and `output_cost` are
   established**; otherwise `total_cost = None`. No partial total is fabricated.
4. If the model has a pricing entry, `response.cost` is an `LLMCost`; its
   unavailable dimensions are `None`. If the model has **no** pricing entry,
   `response.cost` is `None`.
5. Missing prices or usage are never silently coerced to zero.

### 4.4 Pricing status (`response.metadata["cost_status"]`)

Exactly one value per response, derived by this precedence:

| `cost_status` | Condition |
|---|---|
| `pricing_missing` | The model has no pricing entry (`response.cost is None`). |
| `usage_unavailable` | A pricing entry exists, but no cost component can be computed because usage is unavailable (both `input_cost` and `output_cost` are `None`). |
| `partial` | A pricing entry exists and at least one cost component is available, but the full total cannot be established (`total_cost is None`). |
| `complete` | The full total is available (`total_cost` is not `None`). |

Evaluation order: `pricing_missing` → `usage_unavailable` → `partial` →
`complete`. When `response.cost is None` (no entry), the status is
`pricing_missing`.

### 4.5 Rounding and quantization

- All money math uses `decimal.Decimal` under a local decimal context (no
  global-context mutation).
- Tokens are converted via `Decimal(int)`; formulas:
  `input_cost = Decimal(input_tokens) * input_per_1m / Decimal(1_000_000)`
  (analogous for output).
- Each cost is quantized to 12 decimal places with `ROUND_HALF_UP`
  (`Decimal("0.000000000001")`).
- `total_cost` is the quantized sum of the two quantized component costs.
- `LLMCost` exposes `Decimal` values; serialization is a consumer concern.

## 5. Placement and Contract Changes

1. `src/app/llm/contracts.py` — add `LLMCost`; add additive
   `cost: LLMCost | None = None` to `LLMResponse`. `LLMUsage` is unchanged.
2. `src/app/llm/cost.py` (new) — `ModelPricing`, `PricingTable` (`parse`,
   `from_settings`, `empty`), pure `CostCalculator`, and the deterministic
   status values. The calculator returns cost plus the status from §4.4.
3. `src/app/llm/services/llm_service.py` — accept an injected `CostCalculator`
   (default: empty table, so `cost is None` and status `pricing_missing`).
   After a successful response, compute and attach `response.cost` and
   `response.metadata["cost_status"]`. The service must not eagerly call
   `get_settings()`.
4. `src/app/llm/providers/ollama.py` — apply the §3 total-normalization rule.
5. Composition: `PricingTable.from_settings(settings)` is the wiring seam.
   There is currently no composition root constructing `LLMService`; T254 does
   not introduce one. Cost is derived data and never influences retry or
   business decisions.

## 6. Retry / Attempt Scope

Cost and usage apply to the returned successful response only. This is
explicitly **not** total spend across failed or retried attempts. Accounting for
failed-attempt usage (when a provider reports none) is out of scope.

## 7. Configuration

- `LLM_PRICING` — JSON mapping `model -> {input_per_1m, output_per_1m}`, for
  example
  `{"llama3.1:8b": {"input_per_1m": 0.0, "output_per_1m": 0.0}}`.
- `LLM_PRICING_CURRENCY` — default `USD`.
- Validation: malformed JSON, non-numeric values, missing required keys, or
  negative prices raise a clear `ValueError` at parse time. An absent or empty
  `LLM_PRICING` is valid and means cost is always unavailable; no placeholder
  prices are introduced.
- Secrets: none. Documented in `.env.example`; no prices committed as code.

## 8. Observability

On completion, available per request: `usage`, `cost` (with `currency`), and the
deterministic `metadata["cost_status"]` from §4.4, alongside existing
duration/provider/model/status/retry fields. No full prompts or responses; no
customer content; no secrets.

## 9. Testing Requirements

Unit tests must run without a network or live provider and must verify:

- Total derived only when both components are known; `None` when either is
  unknown; provider-reported totals preserved; `0` distinct from unknown.
- Cost for a fully-priced model with full usage (`complete`); pricing present
  but usage missing (`usage_unavailable`); one component available (`partial`);
  model unpriced (`pricing_missing`).
- Partial pricing/usage behavior per §4.3; explicitly configured zero price
  yields `Decimal("0")`.
- `Decimal` quantization to 12 decimal places with `ROUND_HALF_UP`; zero-token
  usage yields zero cost.
- Malformed JSON, negative prices, and missing keys fail clearly; an empty or
  absent table is valid.
- `PricingTable.from_settings` maps configuration correctly; the service is
  testable via an injected calculator.
- Existing LLM tests and the full suite continue to pass.

## 10. Acceptance Criteria

- `LLMUsage` remains provider-sourced; shape unchanged.
- No `total_tokens` is invented when either input or output usage is unknown;
  unknown stays `None`; provider-reported totals are preserved; normalization is
  documented in code.
- `LLMCost` exists with `input_cost`, `output_cost`, `total_cost`
  (`Decimal | None`) and `currency`, exposed via additive
  `LLMResponse.cost: LLMCost | None`.
- Input and output costs are computed independently; `total_cost` is present
  only when both are established.
- Unavailable cost is explicit (`None`); a configured zero price yields
  `Decimal("0")`; missing pricing never becomes zero; empty/absent pricing is
  valid.
- `metadata["cost_status"]` is deterministic and limited to `pricing_missing`,
  `usage_unavailable`, `partial`, and `complete` per §4.4.
- Pricing is externalized via `LLM_PRICING` JSON, per one million tokens, single
  configured currency; malformed JSON and negative prices fail clearly.
- Calculations use `Decimal` with 12-decimal `ROUND_HALF_UP` quantization; no
  global decimal-context mutation.
- `CostCalculator` is pure and injectable; `LLMService` does not eagerly call
  `get_settings()`; pricing is wired via `PricingTable.from_settings`.
- Cost is derived data and never affects retry or business decisions.
- Cost covers only the returned successful response; failed/retried attempt
  accounting is documented as out of scope.
- Focused tests plus the full regression suite pass; no unrelated subsystem is
  redesigned; existing contracts and tests remain compatible.

## 11. Definition of Done

1. This specification is reviewed and approved (status: Approved).
2. T254 is implemented against the §5 file scope only.
3. Focused tests and the full regression suite pass; `git diff --check` is
   clean.
4. The diff is reviewed against this specification; `specs/project-state.md` is
   updated with the task ID, outcome, commit, tests, and exactly one next task.
