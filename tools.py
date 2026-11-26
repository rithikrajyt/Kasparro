"""Simulated tool functions for fetching promotion data from source systems."""

import json
import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def _load_json(filename: str) -> dict | list:
    with open(DATA_DIR / filename) as f:
        return json.load(f)


def get_approved_offer() -> dict:
    return _load_json("approved_offer.json")


def get_shopify_discount() -> dict:
    return _load_json("shopify.json")


def get_klaviyo_campaign() -> dict:
    return _load_json("klaviyo.json")


def get_checkout_observations(rehearsal: str) -> list[dict]:
    filename = f"checkout_rehearsal_{rehearsal.lower()}.json"
    return _load_json(filename)


def request_fresh_checkout(
    product_id: str,
    rehearsal: str,
    simulate_failure: bool = False,
) -> dict:
    """Request a fresh checkout observation for a product.

    In failure simulation mode, raises TimeoutError on both attempts.
    """
    if simulate_failure:
        raise TimeoutError(f"Checkout service timed out for {product_id}")

    fresh_file = DATA_DIR / f"checkout_rehearsal_{rehearsal.lower()}_fresh.json"
    if not fresh_file.exists():
        raise TimeoutError(f"No fresh checkout data available for {product_id}")

    data = json.loads(fresh_file.read_text())
    if isinstance(data, list):
        for obs in data:
            if obs["product_id"] == product_id:
                return obs
        raise TimeoutError(f"No fresh checkout for {product_id}")
    if data["product_id"] == product_id:
        return data
    raise TimeoutError(f"No fresh checkout for {product_id}")
