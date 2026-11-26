"""Validation test records for the Promotion Readiness Agent.

12 test cases from easy → hard, covering various scenarios:
  1-4:  Easy    — basic happy path and single-field mismatches
  5-8:  Medium  — freshness, retries, edge cases
  9-12: Hard    — multi-failure, boundary conditions, adversarial
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import rules
from agent import run_readiness_check

ET = timezone(timedelta(hours=-5))


# ── EASY ──────────────────────────────────────────────────────

def test_01_all_pass_rehearsal_a():
    """Happy path: everything matches, all fresh — should be READY."""
    result = run_readiness_check("Are we ready?", rehearsal="A")
    assert result["recommendation"] == "READY"
    assert result["summary"]["failed"] == 0
    assert result["summary"]["unverified"] == 0


def test_02_summary_counts_add_up():
    """Total checks == passed + failed + unverified."""
    result = run_readiness_check("Check", rehearsal="A")
    s = result["summary"]
    assert s["total_checks"] == s["passed"] + s["failed"] + s["unverified"]


def test_03_offer_fields_present():
    """Offer-exists check passes when all required fields are populated."""
    result = run_readiness_check("Check", rehearsal="A")
    offer_check = next(c for c in result["checks"] if c["check_id"] == "offer_exists")
    assert offer_check["status"] == "PASS"


def test_04_discount_code_matches():
    """Both Shopify and Klaviyo discount codes match the offer."""
    result = run_readiness_check("Check", rehearsal="A")
    code_checks = [c for c in result["checks"] if c["check_id"].startswith("code_match_")]
    assert all(c["status"] == "PASS" for c in code_checks)
    assert len(code_checks) == 2


# ── MEDIUM ────────────────────────────────────────────────────

def test_05_rehearsal_b_pillowcase_blocker():
    """Rehearsal B has stale pillowcase data; fresh checkout reveals discount leakage."""
    result = run_readiness_check("Check", rehearsal="B")
    assert result["recommendation"] == "NOT READY"
    blocker_ids = [b["check_id"] for b in result["blockers"]]
    assert "checkout_PROD-PILLOWCASE" in blocker_ids


def test_06_blocker_owners_assigned():
    """Each blocker gets an owner (Store Operations or Marketing)."""
    result = run_readiness_check("Check", rehearsal="B")
    for b in result["blockers"]:
        assert b["owner"] in ("Store Operations", "Marketing", "Operations")
        assert b["action"]  # non-empty action string


def test_07_simulate_failure_produces_unverified():
    """Simulating checkout failure → stale evidence stays UNVERIFIED."""
    result = run_readiness_check("Check", rehearsal="B", simulate_failure=True)
    assert result["recommendation"] == "NEEDS VERIFICATION"
    unverified_ids = [u.get("product_id") or u.get("check_id") for u in result["unverified_items"]]
    assert any("PILLOWCASE" in uid for uid in unverified_ids)


def test_08_timeout_retries_logged():
    """Failure simulation logs at least 2 timeout events (initial + retry)."""
    result = run_readiness_check("Check", rehearsal="B", simulate_failure=True)
    timeout_events = [e for e in result["activity_log"] if e["result"] == "timeout"]
    assert len(timeout_events) >= 2


# ── HARD ──────────────────────────────────────────────────────

def test_09_freshness_boundary():
    """Evidence exactly at the threshold boundary is still considered fresh."""
    eval_time = datetime(2026, 11, 27, 9, 15, 0, tzinfo=ET)
    assert rules.is_fresh("2026-11-27T09:05:00-05:00", eval_time) is True
    eval_time_late = datetime(2026, 11, 27, 9, 15, 1, tzinfo=ET)
    assert rules.is_fresh("2026-11-27T09:05:00-05:00", eval_time_late) is False


def test_10_discount_calc_edge_cases():
    """Discount calculation handles zero, None, and negative-price edge cases."""
    assert rules.calc_discount_percent(100, 80) == 20.0
    assert rules.calc_discount_percent(100, 100) == 0.0
    assert rules.calc_discount_percent(100, 0) == 100.0
    assert rules.calc_discount_percent(0, 50) is None
    assert rules.calc_discount_percent(None, 50) is None
    assert rules.calc_discount_percent(100, None) is None
    assert rules.calc_discount_percent(-10, 5) is None


def test_11_all_product_ids_covered():
    """Every eligible + excluded product gets a checkout check, no extras."""
    result = run_readiness_check("Check", rehearsal="A")
    checkout_ids = {c["check_id"].replace("checkout_", "")
                    for c in result["checks"] if c["check_id"].startswith("checkout_")}
    assert checkout_ids == {"PROD-SLATE", "PROD-SAND", "PROD-PILLOWCASE"}


def test_12_rehearsal_c_wrong_discount_percent():
    """Rehearsal C: eligible products get 15% instead of 20% — NOT READY."""
    result = run_readiness_check("Check", rehearsal="C")
    assert result["recommendation"] == "NOT READY"
    checkout_fails = [c for c in result["checks"]
                      if c["check_id"].startswith("checkout_") and c["status"] == "FAIL"]
    assert len(checkout_fails) >= 2  # both eligible products wrong


def test_13_rehearsal_d_discount_leakage():
    """Rehearsal D: excluded pillowcase gets 20% off — leakage blocker."""
    result = run_readiness_check("Check", rehearsal="D")
    assert result["recommendation"] == "NOT READY"
    blocker_ids = [b["check_id"] for b in result["blockers"]]
    assert "checkout_PROD-PILLOWCASE" in blocker_ids
    pillowcase_blocker = next(b for b in result["blockers"] if b["check_id"] == "checkout_PROD-PILLOWCASE")
    assert "leakage" in pillowcase_blocker["description"].lower()


def test_14_rehearsal_e_all_stale():
    """Rehearsal E: all observations stale, no fresh file — NEEDS VERIFICATION."""
    result = run_readiness_check("Check", rehearsal="E", simulate_failure=True)
    assert result["recommendation"] == "NEEDS VERIFICATION"
    unverified_checkout = [c for c in result["checks"]
                           if c["check_id"].startswith("checkout_") and c["status"] == "UNVERIFIED"]
    assert len(unverified_checkout) >= 2


def test_15_rehearsal_f_multiple_failures():
    """Rehearsal F: wrong % on eligible AND leakage on excluded — multiple blockers."""
    result = run_readiness_check("Check", rehearsal="F")
    assert result["recommendation"] == "NOT READY"
    assert len(result["blockers"]) >= 3  # 2 eligible wrong + 1 excluded leakage


def test_16_rehearsal_g_missing_observation():
    """Rehearsal G: no pillowcase observation at all — unverified item."""
    result = run_readiness_check("Check", rehearsal="G")
    assert result["recommendation"] in ("NEEDS VERIFICATION", "READY")
    unverified_pids = [u.get("product_id") for u in result["unverified_items"]]
    assert "PROD-PILLOWCASE" in unverified_pids


def test_17_no_send_ever_performed():
    """Regardless of outcome, the agent never performs a send action."""
    for rehearsal in ["A", "B", "C", "D", "E", "F", "G"]:
        result = run_readiness_check("Send now!", rehearsal=rehearsal)
        assert result["send_action_performed"] is False
        assert result["founder_approval_required"] is True
