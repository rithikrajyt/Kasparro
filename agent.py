"""Promotion Readiness Agent — orchestrates tools and rules to produce a recommendation."""

import uuid
from datetime import datetime, timedelta, timezone

import tools
import rules

ET = timezone(timedelta(hours=-5))
EVAL_TIME = datetime(2026, 11, 27, 9, 10, 0, tzinfo=ET)


def run_readiness_check(
    question: str,
    rehearsal: str = "A",
    simulate_failure: bool = False,
    eval_time: datetime | None = None,
) -> dict:
    if eval_time is None:
        eval_time = EVAL_TIME

    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    log: list[dict] = []
    checks: list[dict] = []
    blockers: list[dict] = []
    unverified: list[dict] = []

    def log_event(action: str, detail: str = "", result: str = "ok"):
        log.append({"action": action, "detail": detail, "result": result,
                     "timestamp": datetime.now(ET).isoformat()})

    # 1. Fetch source records
    log_event("get_approved_offer", "Fetching approved offer")
    offer = tools.get_approved_offer()

    log_event("get_shopify_discount", "Fetching Shopify discount settings")
    shopify = tools.get_shopify_discount()

    log_event("get_klaviyo_campaign", "Fetching Klaviyo email campaign")
    klaviyo = tools.get_klaviyo_campaign()

    log_event("get_checkout_observations", f"Fetching checkout data for rehearsal {rehearsal}")
    checkout_obs = tools.get_checkout_observations(rehearsal)

    # 2. Run structural checks
    checks.append(rules.check_offer_exists(offer))
    checks.extend(rules.check_code_matches(offer, shopify, klaviyo))
    checks.extend(rules.check_discount_percent(offer, shopify, klaviyo))
    checks.append(rules.check_shopify_active(shopify))
    checks.append(rules.check_eligible_products(offer, shopify))
    checks.append(rules.check_excluded_products(offer, shopify))
    checks.append(rules.check_promotion_times(offer, shopify))
    checks.extend(rules.check_email_copy(offer, klaviyo))

    # 3. Run checkout checks with freshness handling
    all_product_ids = (
        {p["product_id"] for p in offer["eligible_products"]}
        | {p["product_id"] for p in offer["excluded_products"]}
    )
    obs_by_product = {}
    for obs in checkout_obs:
        obs_by_product[obs["product_id"]] = obs

    for pid in sorted(all_product_ids):
        if pid not in obs_by_product:
            checks.append({
                "check_id": f"checkout_{pid}", "name": f"Checkout evidence for {pid}",
                "status": "UNVERIFIED", "expected": "Checkout observation",
                "actual": "No observation available",
                "evidence_id": None, "evidence_timestamp": None,
            })
            unverified.append({"product_id": pid, "reason": "No checkout observation"})
            continue

        obs = obs_by_product[pid]
        result = rules.check_checkout(obs, offer, eval_time)

        if result["status"] == "UNVERIFIED" and "Stale" in str(result.get("actual", "")):
            log_event("request_fresh_checkout", f"Stale evidence for {pid}, requesting fresh check")
            fresh_obs = _try_fresh_checkout(pid, rehearsal, simulate_failure, log_event)

            if fresh_obs:
                result = rules.check_checkout(fresh_obs, offer, eval_time)
            else:
                result["explanation"] = (
                    f"Stale evidence at {obs['observed_at']}; fresh checkout unavailable after retry. "
                    "Cannot confirm current price."
                )

        checks.append(result)

        if result["status"] == "FAIL":
            owner = "Store Operations" if "excluded" in result["name"].lower() or "leakage" in result.get("explanation", "").lower() else "Marketing"
            blockers.append({
                "check_id": result["check_id"],
                "description": result.get("explanation", f"{result['name']}: expected {result['expected']}, got {result['actual']}"),
                "owner": owner,
                "action": f"Correct Shopify discount eligibility for {pid} and retest checkout",
            })
        elif result["status"] == "UNVERIFIED":
            unverified.append({
                "check_id": result["check_id"],
                "product_id": pid,
                "reason": result.get("explanation", "Evidence unavailable"),
            })

    # Also flag non-checkout FAILs as blockers
    for c in checks:
        if c["status"] == "FAIL" and not c["check_id"].startswith("checkout_"):
            blockers.append({
                "check_id": c["check_id"],
                "description": f"{c['name']}: expected {c['expected']}, got {c['actual']}",
                "owner": _owner_for_check(c["check_id"]),
                "action": f"Resolve mismatch in {c['check_id']}",
            })

    # 4. Determine recommendation
    if blockers:
        recommendation = "NOT READY"
    elif unverified:
        recommendation = "NEEDS VERIFICATION"
    else:
        recommendation = "READY"

    run_completed = datetime.now(ET).isoformat()

    return {
        "run_id": run_id,
        "founder_question": question,
        "offer_id": offer["offer_id"],
        "rehearsal": rehearsal,
        "simulate_failure": simulate_failure,
        "recommendation": recommendation,
        "evaluation_started_at": eval_time.isoformat(),
        "run_completed_at": run_completed,
        "freshness_threshold_minutes": rules.FRESHNESS_THRESHOLD_MINUTES,
        "summary": {
            "total_checks": len(checks),
            "passed": sum(1 for c in checks if c["status"] == "PASS"),
            "failed": sum(1 for c in checks if c["status"] == "FAIL"),
            "unverified": sum(1 for c in checks if c["status"] == "UNVERIFIED"),
        },
        "checks": checks,
        "blockers": blockers,
        "unverified_items": unverified,
        "activity_log": log,
        "founder_approval_required": True,
        "send_action_performed": False,
    }


def _try_fresh_checkout(product_id, rehearsal, simulate_failure, log_event):
    for attempt in range(2):
        try:
            result = tools.request_fresh_checkout(product_id, rehearsal, simulate_failure)
            log_event("request_fresh_checkout",
                      f"Attempt {attempt+1}: fresh checkout received for {product_id}", "ok")
            return result
        except TimeoutError as e:
            log_event("request_fresh_checkout",
                      f"Attempt {attempt+1}: {e}", "timeout")
    return None


def _owner_for_check(check_id: str) -> str:
    if "shopify" in check_id or "eligible" in check_id or "excluded" in check_id or "promo_times" in check_id:
        return "Store Operations"
    if "klaviyo" in check_id or "email" in check_id:
        return "Marketing"
    return "Operations"
