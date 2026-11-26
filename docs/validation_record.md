# Validation Record

All results below were produced by running the actual implementation (`python3 run_agent.py` and `streamlit run app.py`). The agent runs 15 checks per execution across four source systems.

## Core Scenarios (required by assignment)

| Case | Expected | Actual | Checks | Supporting Evidence |
|---|---|---|---|---|
| **Rehearsal A** | READY | ✅ READY | 15 pass, 0 fail, 0 unverified | Slate $100→$80 (20% off, 9:05 AM), Sand $120→$96 (20% off, 9:06 AM), Pillowcase $40→$40 (0% off, 9:07 AM). All evidence fresh at 9:10 AM eval time. No blockers. Discount codes, percentages, eligible/excluded products, promo times, email copy all match. |
| **Rehearsal B** | NOT READY | ❌ NOT READY | 14 pass, 1 fail, 0 unverified | Pillowcase 8:40 AM observation stale at 9:10 AM eval → agent requests fresh checkout → 9:11 AM result shows $40→$32 (20% discount on excluded product). Blocker: `[Store Operations] Excluded product is receiving 20.0% discount — discount leakage. Action: Correct Shopify discount eligibility for PROD-PILLOWCASE and retest checkout.` |
| **Failure Case** (B + simulate-failure) | NEEDS VERIFICATION | ⚠️ NEEDS VERIFICATION | 14 pass, 0 fail, 1 unverified | Pillowcase 8:40 AM stale → fresh checkout request times out → retry times out → evidence remains unverified. Activity log shows 2 timeout events. Stale observation not treated as current proof. |

### Edge case: Rehearsal A + simulate-failure

| Case | Expected | Actual | Note |
|---|---|---|---|
| **A + simulate-failure** | READY | ✅ READY | All evidence in Rehearsal A is fresh (observed 9:05–9:07, eval 9:10), so no fresh-checkout request is triggered and the simulate-failure flag has no effect. The UI displays a warning: *"Simulate failure was checked but had no effect — all checkout evidence in this rehearsal is already fresh."* |

## Extended Scenarios (additional validation)

| Case | Expected | Actual | Checks | Supporting Evidence |
|---|---|---|---|---|
| **Rehearsal C** — Wrong discount % | NOT READY | ❌ NOT READY | 13 pass, 2 fail | Slate $100→$85 (15%) and Sand $120→$102 (15%) instead of expected 20%. Both eligible products fail checkout price check. 2 blockers raised to Marketing. |
| **Rehearsal D** — Discount leakage | NOT READY | ❌ NOT READY | 14 pass, 1 fail | Excluded Pillowcase $40→$32 (20% off). Blocker with "discount leakage" flagged to Store Operations. Eligible products correctly priced. |
| **Rehearsal E** — All stale, no fresh data | NEEDS VERIFICATION | ⚠️ NEEDS VERIFICATION | 12 pass, 0 fail, 3 unverified | All checkout observations older than 10 min threshold (observed 8:50–8:55, eval 9:10). No fresh checkout file available → all 3 products unverified after retry timeouts. |
| **Rehearsal F** — Multiple failures | NOT READY | ❌ NOT READY | 12 pass, 3 fail | Both eligible products get wrong % (15%) AND excluded Pillowcase gets 20% off. 3 blockers raised — covers simultaneous pricing and leakage errors. |
| **Rehearsal G** — Missing observation | NEEDS VERIFICATION | ⚠️ NEEDS VERIFICATION | 14 pass, 0 fail, 1 unverified | No checkout observation for PROD-PILLOWCASE at all. Unverified item raised with reason "No checkout observation". Eligible products pass normally. |

## Summary of All Outcomes

| Rehearsal | Recommendation | Pass | Fail | Unverified | Key Failure Mode |
|---|---|---|---|---|---|
| A | READY | 15 | 0 | 0 | — (happy path) |
| B | NOT READY | 14 | 1 | 0 | Stale → fresh → leakage discovered |
| B + failure | NEEDS VERIFICATION | 14 | 0 | 1 | Stale → timeout → unverifiable |
| C | NOT READY | 13 | 2 | 0 | Wrong discount % on eligible products |
| D | NOT READY | 14 | 1 | 0 | Leakage on excluded product |
| E | NEEDS VERIFICATION | 12 | 0 | 3 | All evidence stale, no fresh source |
| F | NOT READY | 12 | 3 | 0 | Wrong % + leakage (multi-failure) |
| G | NEEDS VERIFICATION | 14 | 0 | 1 | Missing checkout observation |

## Automated Test Suite

23 tests pass covering all scenarios above plus edge cases (freshness boundary at exactly 10 min, discount calculation with zero/None/negative prices, summary arithmetic, blocker owner assignment, no-send invariant across all 7 rehearsals).

```
tests/test_agent.py ..................  6 passed
tests/test_validation_records.py .... 17 passed
─────────────────────────────────────
Total:                                23 passed
```

## Most Important Gap Before Live Pilot

**Authenticated live integrations and checkout verification.** The MVP uses simulated JSON data files. Before a production pilot, the agent needs:

1. **Authenticated Shopify and Klaviyo API integrations** to fetch real-time source records instead of static files
2. **Reliable live checkout verification** — headless browser or Shopify Storefront API-based price check to replace simulated observations
3. **Persistent evidence and run history** for audit trails and decision traceability over time
4. **Monitoring and alerting** on tool failures, retry rates, and recommendation accuracy to catch degradation before it affects launch decisions
