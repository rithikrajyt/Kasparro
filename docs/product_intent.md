# Product Intent Document — Promotion Readiness Agent

## Intended Outcome

Enable the founder to ask "Are we ready to send?" before a Shopify promotion launch and receive an evidence-backed recommendation within seconds. The agent cross-checks the approved offer, Shopify discount configuration, Klaviyo email draft, and actual checkout prices, then surfaces blockers with assigned owners and next actions.

**Primary user:** Founder (final approver for campaign sends).

## Scope

**In scope:** Simulated tool-based checks against four source systems (approved offer, Shopify, Klaviyo, checkout). Deterministic validation of discount codes, percentages, eligible/excluded products, promotion timing, email accuracy, and checkout pricing. Freshness-aware evidence handling with automatic fresh-checkout requests. Failure handling with retry and graceful degradation.

**Out of scope (non-goals):** Live API integrations, authentication, database persistence, campaign sending or editing, autonomous approval, LLM-based reasoning, cloud deployment.

## Founder Decision Boundary

The agent recommends; the founder decides. The system explicitly sets `founder_approval_required: true` and `send_action_performed: false`. No send capability exists.

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

JSON report containing: run_id, recommendation (READY / NOT READY / NEEDS VERIFICATION), all checks with status/expected/actual/evidence, blockers with owner and action, unverified items, and agent activity log.

## Missing, Stale, and Conflicting Evidence

| Condition | Behaviour |
|---|---|
| **Missing** checkout observation | Check marked UNVERIFIED; recommendation escalated to NEEDS VERIFICATION |
| **Stale** evidence (>10 min before evaluation) | Agent requests fresh checkout; uses fresh result if available |
| **Fresh check unavailable** | Retry once; if still unavailable, mark UNVERIFIED (stale evidence is not treated as current) |
| **Conflicting** evidence (e.g. excluded product receives discount) | Check marked FAIL; blocker raised with owner and remediation action |
| **Missing required field** | Check marked UNVERIFIED; no silent pass |

**Freshness threshold:** 10 minutes (explicit MVP assumption, documented in output).

## Recommendation Policy

| State | Condition | Precedence |
|---|---|---|
| **NOT READY** | ≥1 confirmed business-rule violation | Highest |
| **NEEDS VERIFICATION** | No confirmed blocker, but ≥1 mandatory check is unverified/missing/stale | Middle |
| **READY** | All mandatory checks pass with fresh evidence | Lowest |

A confirmed blocker always takes precedence. Missing data never counts as a pass.

## MVP Pass Criteria

1. Rehearsal A → READY (all checks pass, evidence fresh)
2. Rehearsal B → NOT READY (stale evidence triggers fresh check; fresh check reveals discount leakage on excluded product)
3. Failure case (B + simulate-failure) → NEEDS VERIFICATION (fresh checkout times out after retry; stale evidence not treated as proof)
4. Extended rehearsals C–G cover wrong discount %, direct leakage, all-stale data, multi-failure, and missing observations
5. Every recommendation traceable to source records and timestamps
6. Founder retains final approval; no send action exists
7. 23 automated tests pass covering all scenarios and edge cases
8. Reviewer can install dependencies and run the app from README instructions
