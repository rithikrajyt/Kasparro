"""Tests for the Promotion Readiness Agent."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import run_readiness_check


def test_rehearsal_a_ready():
    result = run_readiness_check("Are we ready to send?", rehearsal="A")
    assert result["recommendation"] == "READY"
    assert result["blockers"] == []
    assert result["unverified_items"] == []
    assert result["founder_approval_required"] is True
    assert result["send_action_performed"] is False


def test_rehearsal_b_not_ready():
    result = run_readiness_check("Are we ready to send?", rehearsal="B")
    assert result["recommendation"] == "NOT READY"
    assert len(result["blockers"]) >= 1
    blocker_ids = [b["check_id"] for b in result["blockers"]]
    assert "checkout_PROD-PILLOWCASE" in blocker_ids
    pillowcase_blocker = next(b for b in result["blockers"] if b["check_id"] == "checkout_PROD-PILLOWCASE")
    assert pillowcase_blocker["owner"] == "Store Operations"


def test_failure_needs_verification():
    result = run_readiness_check("Are we ready to send?", rehearsal="B", simulate_failure=True)
    assert result["recommendation"] == "NEEDS VERIFICATION"
    assert any(u.get("product_id") == "PROD-PILLOWCASE" or u.get("check_id") == "checkout_PROD-PILLOWCASE"
               for u in result["unverified_items"])
    timeout_events = [e for e in result["activity_log"] if e["result"] == "timeout"]
    assert len(timeout_events) >= 2, "Expected at least 2 timeout events (initial + retry)"


def test_freshness_threshold_documented():
    result = run_readiness_check("Are we ready to send?", rehearsal="A")
    assert result["freshness_threshold_minutes"] == 10


def test_no_send_action():
    for rehearsal in ["A", "B"]:
        result = run_readiness_check("Check", rehearsal=rehearsal)
        assert result["send_action_performed"] is False
        assert result["founder_approval_required"] is True


def test_all_products_checked():
    result = run_readiness_check("Are we ready to send?", rehearsal="A")
    checkout_checks = [c for c in result["checks"] if c["check_id"].startswith("checkout_")]
    product_ids = {c["check_id"].replace("checkout_", "") for c in checkout_checks}
    assert "PROD-SLATE" in product_ids
    assert "PROD-SAND" in product_ids
    assert "PROD-PILLOWCASE" in product_ids
