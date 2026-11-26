# Product Intent Document — Promotion Readiness Agent

## Intended Outcome

Enable the founder to ask "Are we ready to send?" before a Shopify promotion launch and receive an evidence-backed recommendation within seconds. The agent cross-checks the approved offer, Shopify discount configuration, Klaviyo email draft, and actual checkout prices, then surfaces blockers with assigned owners and next actions.

**Primary user:** Founder (final approver for campaign sends).

## Scope

**In scope:** Simulated tool-based checks against four source systems (approved offer, Shopify, Klaviyo, checkout). Deterministic validation of discount codes, percentages, eligible/excluded products, promotion timing, email accuracy, and checkout pricing. Freshness-aware evidence handling with automatic fresh-checkout requests. Failure handling with retry and graceful degradation. Seven rehearsal scenarios (A–G) exercising happy path, stale data, wrong percentages, discount leakage, multi-failure, and missing observations. Streamlit UI with tabbed check views, KPI tiles, blocker cards, activity log, and downloadable JSON reports. CLI runner for scripted/CI use.

**Out of scope (non-goals):** Live API integrations, authentication, database persistence, campaign sending or editing, autonomous approval, LLM-based reasoning.

## Founder Decision Boundary

The agent recommends; the founder decides. The system explicitly sets `founder_approval_required: true` and `send_action_performed: false` on every run, regardless of outcome. No send capability exists in the codebase.

## Data Contracts

### Inputs (per source system)

| Source | Key Fields | Identifiers | Timestamps |
|---|---|---|---|
| Approved Offer | discount_code, discount_percent, eligible/excluded products | offer_id, product_id | promotion_start/end (TZ-aware ET) |
| Shopify | discount_code, discount_percent, status, eligible/excluded products | discount_id, product_id | starts_at/ends_at (TZ-aware ET) |
| Klaviyo | email_copy, discount_code, products_mentioned, main_link | campaign_id, product_id | scheduled_at (TZ-aware ET) |
| Checkout | before_price, after_price, discount_code | checkout_id, product_id | observed_at (TZ-aware ET) |

All records carry `source_system`, `record_id`, and timezone-aware timestamps. Product comparisons use stable `product_id` identifiers.

### Output

JSON report containing: run_id, recommendation (READY / NOT READY / NEEDS VERIFICATION), all checks with status/expected/actual/evidence, blockers with owner and action, unverified items, activity log, and metadata (`founder_approval_required`, `send_action_performed`, `freshness_threshold_minutes`).

## Missing, Stale, and Conflicting Evidence

| Condition | Behaviour |
|---|---|
| **Missing** checkout observation | Check marked UNVERIFIED; recommendation escalated to NEEDS VERIFICATION |
| **Stale** evidence (>10 min before evaluation) | Agent requests fresh checkout; uses fresh result if available |
| **Fresh check unavailable** | Retry once; if still unavailable, mark UNVERIFIED (stale evidence is not treated as current) |
| **Conflicting** evidence (e.g. excluded product receives discount) | Check marked FAIL; blocker raised with owner and remediation action |
| **Missing required field** in offer | Check marked FAIL; offer_exists check surfaces missing fields |
| **Simulate-failure with no stale data** | UI warns that the flag had no effect (no fresh-checkout request was needed) |

**Freshness threshold:** 10 minutes (explicit MVP assumption, documented in every output).

## Recommendation Policy

| State | Condition | Precedence |
|---|---|---|
| **NOT READY** | ≥1 confirmed business-rule violation | Highest |
| **NEEDS VERIFICATION** | No confirmed blocker, but ≥1 mandatory check is unverified/missing/stale | Middle |
| **READY** | All mandatory checks pass with fresh evidence | Lowest |

A confirmed blocker always takes precedence. Missing data never counts as a pass.

## Checks Performed (15 per run)

| # | Check | Source Systems |
|---|---|---|
| 1 | Approved offer has all required fields | Offer |
| 2–3 | Discount code matches (Shopify, Klaviyo) | Offer ↔ Shopify, Offer ↔ Klaviyo |
| 4–5 | Discount percentage matches (Shopify, Klaviyo) | Offer ↔ Shopify, Offer ↔ Klaviyo |
| 6 | Shopify discount is active | Shopify |
| 7 | Eligible products match | Offer ↔ Shopify |
| 8 | Excluded products match | Offer ↔ Shopify |
| 9 | Promotion times match | Offer ↔ Shopify |
| 10 | Email product coverage matches eligible | Offer ↔ Klaviyo |
| 11 | Email main link targets eligible product | Klaviyo |
| 12 | Email scheduled within promotion window | Offer ↔ Klaviyo |
| 13–15 | Checkout price per product (eligible get discount, excluded don't) | Offer ↔ Checkout |

## MVP Pass Criteria

1. Rehearsal A → READY (all 15 checks pass, evidence fresh)
2. Rehearsal B → NOT READY (stale evidence triggers fresh check; fresh check reveals discount leakage on excluded product)
3. Failure case (B + simulate-failure) → NEEDS VERIFICATION (fresh checkout times out after retry; stale evidence not treated as proof)
4. Extended rehearsals C–G cover wrong discount %, direct leakage, all-stale data, multi-failure, and missing observations
5. Every recommendation traceable to source records and timestamps
6. Founder retains final approval; no send action exists
7. 23 automated tests pass covering all scenarios and edge cases
8. Reviewer can install dependencies and run the app from README instructions
