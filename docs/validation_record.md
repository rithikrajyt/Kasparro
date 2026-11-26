# Validation Record

All results below were produced by running the actual implementation.

## Core Scenarios (required by assignment)

| Case | Expected | Actual | Supporting Evidence |
|---|---|---|---|
| **Rehearsal A** | READY | ✅ READY | 15/15 checks pass. Slate $100→$80 (20% off, 9:05 AM), Sand $120→$96 (20% off, 9:06 AM), Pillowcase $40→$40 (0% off, 9:07 AM). All evidence fresh at 9:10 AM eval time. No blockers. |
| **Rehearsal B** | NOT READY | ❌ NOT READY | 14 pass, 1 fail. Pillowcase 8:40 AM observation stale at 9:10 AM → agent requests fresh checkout → 9:11 AM result shows $40→$32 (20% discount on excluded product). Blocker: Store Operations must correct Shopify discount eligibility for PROD-PILLOWCASE and retest. |
| **Failure Case** (B + checkout timeout) | NEEDS VERIFICATION | ⚠️ NEEDS VERIFICATION | 14 pass, 1 unverified. Pillowcase 8:40 AM stale → fresh checkout request times out → retry times out → evidence remains unverified. Stale observation not treated as current proof. Activity log shows 2 timeout events. |

## Extended Scenarios (additional validation)

| Case | Expected | Actual | Supporting Evidence |
|---|---|---|---|
| **Rehearsal C** — Wrong discount % | NOT READY | ❌ NOT READY | 13 pass, 2 fail. Slate $100→$85 (15%) and Sand $120→$102 (15%) instead of expected 20%. Both eligible products fail checkout price check. |
| **Rehearsal D** — Discount leakage | NOT READY | ❌ NOT READY | 14 pass, 1 fail. Excluded Pillowcase $40→$32 (20% off). Blocker with "discount leakage" flagged to Store Operations. |
| **Rehearsal E** — All stale + no fresh data | NEEDS VERIFICATION | ⚠️ NEEDS VERIFICATION | 12 pass, 3 unverified. All checkout observations older than 10 min threshold. No fresh checkout file available → all 3 products unverified. |
| **Rehearsal F** — Multiple failures | NOT READY | ❌ NOT READY | 12 pass, 3 fail. Both eligible products get wrong % (15%) AND excluded Pillowcase gets 20% off. 3 blockers raised. |
| **Rehearsal G** — Missing observation | NEEDS VERIFICATION | ⚠️ NEEDS VERIFICATION | 14 pass, 1 unverified. No checkout observation for PROD-PILLOWCASE at all. Unverified item raised with reason "No checkout observation". |

## Automated Test Suite

23 tests pass covering all scenarios above plus edge cases (freshness boundary, discount calculation with None/zero/negative, summary arithmetic, owner assignment, no-send invariant across all rehearsals).

```
tests/test_agent.py ............. 6 passed
tests/test_validation_records.py ............. 17 passed
```

## Most Important Gap Before Live Pilot

**Authenticated live integrations and checkout verification.** The MVP uses simulated data files. Before a production pilot, the agent needs: (1) authenticated Shopify and Klaviyo API integrations to fetch real-time source records, (2) reliable live checkout verification (headless browser or Shopify API-based price check), (3) persistent evidence and run history for audit trails, and (4) monitoring of tool failures, retries, and decision accuracy over time.
