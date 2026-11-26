"""Business rules and validation checks for promotion readiness."""

from datetime import datetime, timedelta, timezone

FRESHNESS_THRESHOLD_MINUTES = 10

ET = timezone(timedelta(hours=-5))


def parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def is_fresh(observed_at: str, eval_time: datetime) -> bool:
    obs = parse_dt(observed_at)
    return (eval_time - obs).total_seconds() <= FRESHNESS_THRESHOLD_MINUTES * 60


def calc_discount_percent(before: float, after: float) -> float | None:
    if before is None or after is None or before <= 0:
        return None
    return round((before - after) / before * 100, 2)


def check_offer_exists(offer: dict) -> dict:
    required = ["offer_id", "discount_code", "discount_percent", "eligible_products",
                 "excluded_products", "promotion_start", "promotion_end"]
    missing = [f for f in required if not offer.get(f)]
    if missing:
        return _fail("offer_exists", "Approved offer has all required fields",
                      "All present", f"Missing: {missing}", offer.get("record_id"))
    return _pass("offer_exists", "Approved offer has all required fields",
                  "All present", "All present", offer.get("record_id"))


def check_code_matches(offer: dict, shopify: dict, klaviyo: dict) -> list[dict]:
    checks = []
    expected = offer["discount_code"]
    for name, source, actual in [
        ("Shopify discount code", "shopify", shopify.get("discount_code")),
        ("Klaviyo email code", "klaviyo", klaviyo.get("discount_code_in_email")),
    ]:
        cid = f"code_match_{source}"
        if actual == expected:
            checks.append(_pass(cid, f"{name} matches approved offer", expected, actual,
                                shopify.get("record_id") if source == "shopify" else klaviyo.get("record_id")))
        else:
            checks.append(_fail(cid, f"{name} matches approved offer", expected, actual,
                                shopify.get("record_id") if source == "shopify" else klaviyo.get("record_id")))
    return checks


def check_discount_percent(offer: dict, shopify: dict, klaviyo: dict) -> list[dict]:
    checks = []
    expected = offer["discount_percent"]
    for name, source, actual in [
        ("Shopify discount %", "shopify", shopify.get("discount_percent")),
        ("Klaviyo claimed %", "klaviyo", klaviyo.get("discount_percent_claimed")),
    ]:
        cid = f"discount_pct_{source}"
        if actual == expected:
            checks.append(_pass(cid, f"{name} matches approved offer", f"{expected}%", f"{actual}%",
                                shopify.get("record_id") if source == "shopify" else klaviyo.get("record_id")))
        else:
            checks.append(_fail(cid, f"{name} matches approved offer", f"{expected}%", f"{actual}%",
                                shopify.get("record_id") if source == "shopify" else klaviyo.get("record_id")))
    return checks


def check_shopify_active(shopify: dict) -> dict:
    status = shopify.get("status", "")
    if status == "active":
        return _pass("shopify_active", "Shopify discount is active", "active", status, shopify["record_id"])
    return _fail("shopify_active", "Shopify discount is active", "active", status, shopify["record_id"])


def check_eligible_products(offer: dict, shopify: dict) -> dict:
    offer_ids = {p["product_id"] for p in offer["eligible_products"]}
    shopify_ids = {p["product_id"] for p in shopify.get("eligible_products", [])}
    if offer_ids == shopify_ids:
        return _pass("eligible_match", "Shopify eligible products match approved offer",
                      sorted(offer_ids), sorted(shopify_ids), shopify["record_id"])
    return _fail("eligible_match", "Shopify eligible products match approved offer",
                  sorted(offer_ids), sorted(shopify_ids), shopify["record_id"])


def check_excluded_products(offer: dict, shopify: dict) -> dict:
    offer_ids = {p["product_id"] for p in offer["excluded_products"]}
    shopify_ids = {p["product_id"] for p in shopify.get("excluded_products", [])}
    if offer_ids == shopify_ids:
        return _pass("excluded_match", "Shopify excluded products match approved offer",
                      sorted(offer_ids), sorted(shopify_ids), shopify["record_id"])
    return _fail("excluded_match", "Shopify excluded products match approved offer",
                  sorted(offer_ids), sorted(shopify_ids), shopify["record_id"])


def check_promotion_times(offer: dict, shopify: dict) -> dict:
    offer_start = offer["promotion_start"]
    offer_end = offer["promotion_end"]
    shopify_start = shopify.get("starts_at")
    shopify_end = shopify.get("ends_at")
    if offer_start == shopify_start and offer_end == shopify_end:
        return _pass("promo_times", "Shopify promotion times match approved offer",
                      f"{offer_start} — {offer_end}", f"{shopify_start} — {shopify_end}", shopify["record_id"])
    return _fail("promo_times", "Shopify promotion times match approved offer",
                  f"{offer_start} — {offer_end}", f"{shopify_start} — {shopify_end}", shopify["record_id"])


def check_email_copy(offer: dict, klaviyo: dict) -> list[dict]:
    checks = []
    email_products = {p["product_id"] for p in klaviyo.get("products_mentioned", [])}
    offer_eligible = {p["product_id"] for p in offer["eligible_products"]}
    if email_products == offer_eligible:
        checks.append(_pass("email_products", "Email product coverage matches eligible products",
                            sorted(offer_eligible), sorted(email_products), klaviyo["record_id"]))
    else:
        checks.append(_fail("email_products", "Email product coverage matches eligible products",
                            sorted(offer_eligible), sorted(email_products), klaviyo["record_id"]))

    link_pid = klaviyo.get("main_link_product_id")
    if link_pid in offer_eligible:
        checks.append(_pass("email_link", "Email main link targets an eligible product",
                            "Eligible product", f"{link_pid} (eligible)", klaviyo["record_id"]))
    else:
        checks.append(_fail("email_link", "Email main link targets an eligible product",
                            "Eligible product", f"{link_pid} (not eligible)", klaviyo["record_id"]))

    sched = klaviyo.get("scheduled_at")
    promo_start = parse_dt(offer["promotion_start"])
    promo_end = parse_dt(offer["promotion_end"])
    if sched:
        sched_dt = parse_dt(sched)
        if promo_start <= sched_dt <= promo_end:
            checks.append(_pass("email_schedule", "Email scheduled within promotion window",
                                f"{offer['promotion_start']} — {offer['promotion_end']}", sched, klaviyo["record_id"]))
        else:
            checks.append(_fail("email_schedule", "Email scheduled within promotion window",
                                f"{offer['promotion_start']} — {offer['promotion_end']}", sched, klaviyo["record_id"]))
    return checks


def check_checkout(obs: dict, offer: dict, eval_time: datetime) -> dict:
    pid = obs["product_id"]
    eligible_ids = {p["product_id"] for p in offer["eligible_products"]}
    excluded_ids = {p["product_id"] for p in offer["excluded_products"]}

    before = obs.get("before_price")
    after = obs.get("after_price")
    actual_pct = calc_discount_percent(before, after)

    fresh = is_fresh(obs["observed_at"], eval_time)
    cid = f"checkout_{pid}"

    if not fresh:
        return _unverified(cid, f"Checkout price for {obs.get('product_name', pid)}",
                           "Fresh evidence", f"Stale (observed {obs['observed_at']})",
                           obs["record_id"], obs["observed_at"],
                           f"Evidence is older than {FRESHNESS_THRESHOLD_MINUTES} min — fresh check required")

    if pid in eligible_ids:
        expected_pct = offer["discount_percent"]
        if actual_pct == expected_pct:
            return _pass(cid, f"Checkout price for {obs.get('product_name', pid)}",
                         f"{expected_pct}% off", f"{actual_pct}% off (${before}→${after})",
                         obs["record_id"], obs["observed_at"])
        else:
            return _fail(cid, f"Checkout price for {obs.get('product_name', pid)}",
                         f"{expected_pct}% off", f"{actual_pct}% off (${before}→${after})",
                         obs["record_id"], obs["observed_at"])
    elif pid in excluded_ids:
        if actual_pct == 0:
            return _pass(cid, f"Checkout price for {obs.get('product_name', pid)} (excluded)",
                         "0% off (full price)", f"{actual_pct}% off (${before}→${after})",
                         obs["record_id"], obs["observed_at"])
        else:
            return _fail(cid, f"Checkout price for {obs.get('product_name', pid)} (excluded)",
                         "0% off (full price)", f"{actual_pct}% off (${before}→${after})",
                         obs["record_id"], obs["observed_at"],
                         f"Excluded product is receiving {actual_pct}% discount — discount leakage")
    else:
        return _unverified(cid, f"Checkout price for {obs.get('product_name', pid)}",
                           "Known product", f"Unknown product {pid}",
                           obs["record_id"], obs["observed_at"])


def _pass(check_id, name, expected, actual, evidence_id, evidence_ts=None):
    return {"check_id": check_id, "name": name, "status": "PASS",
            "expected": expected, "actual": actual,
            "evidence_id": evidence_id, "evidence_timestamp": evidence_ts}


def _fail(check_id, name, expected, actual, evidence_id, evidence_ts=None, explanation=None):
    r = {"check_id": check_id, "name": name, "status": "FAIL",
         "expected": expected, "actual": actual,
         "evidence_id": evidence_id, "evidence_timestamp": evidence_ts}
    if explanation:
        r["explanation"] = explanation
    return r


def _unverified(check_id, name, expected, actual, evidence_id, evidence_ts=None, explanation=None):
    r = {"check_id": check_id, "name": name, "status": "UNVERIFIED",
         "expected": expected, "actual": actual,
         "evidence_id": evidence_id, "evidence_timestamp": evidence_ts}
    if explanation:
        r["explanation"] = explanation
    return r
