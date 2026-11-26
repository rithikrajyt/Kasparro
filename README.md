# Promotion Readiness Agent — Kasparro MVP

A lightweight agent that checks whether a Shopify promotion is ready to send by cross-validating the approved offer, Shopify discount settings, Klaviyo email draft, and checkout prices. It surfaces blockers with owners and actions, and the founder retains final approval.

## Architecture

The agent is a deterministic Python orchestrator with four simulated tool functions (approved offer, Shopify, Klaviyo, checkout). It runs 15 validation checks covering code/discount/product/timing/email/checkout matching, evaluates evidence freshness (10-minute threshold), requests fresh checkout when stale data is detected, and produces a recommendation of READY, NOT READY, or NEEDS VERIFICATION. No LLM, database, or external API is required.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run — Streamlit UI

```bash
streamlit run app.py
```

## Run — CLI

```bash
# Rehearsal A (expected: READY)
python3 run_agent.py --rehearsal A

# Rehearsal B (expected: NOT READY — discount leakage on excluded product)
python3 run_agent.py --rehearsal B

# Failure case (expected: NEEDS VERIFICATION — checkout timeout after retry)
python3 run_agent.py --rehearsal B --simulate-failure

# Save JSON output
python3 run_agent.py --rehearsal A --output outputs/rehearsal_a.json
```

## Run Tests

```bash
pytest tests/ -v
```

## Expected Outcomes

| Rehearsal | Recommendation | Scenario |
|---|---|---|
| A | READY | All 15 checks pass with fresh evidence |
| B | NOT READY | Stale Pillowcase checkout → fresh check reveals discount leakage on excluded product |
| B + `--simulate-failure` | NEEDS VERIFICATION | Fresh checkout times out + retry fails; stale evidence not treated as proof |
| C | NOT READY | Wrong discount % on eligible products (15% instead of 20%) |
| D | NOT READY | Excluded Pillowcase receives 20% discount (leakage) |
| E | NEEDS VERIFICATION | All checkout observations stale, no fresh data available |
| F | NOT READY | Both wrong % on eligible AND leakage on excluded (multi-failure) |
| G | NEEDS VERIFICATION | Missing Pillowcase checkout observation entirely |

## Project Structure

```
├── app.py              # Streamlit UI
├── agent.py            # Orchestrator — runs checks, produces recommendation
├── tools.py            # Simulated source-system tool functions
├── rules.py            # Business rules and validation logic
├── run_agent.py        # CLI runner
├── requirements.txt
├── data/               # Simulated source records (JSON)
├── tests/              # pytest test suite
├── docs/               # Product Intent Document & Validation Record
└── outputs/            # JSON reports from runs
```

## Known Limitations

- All integrations are **simulated** using local JSON files — no live Shopify, Klaviyo, or checkout APIs.
- Freshness threshold (10 min) is an MVP assumption, not a production-validated value.
- No authentication, persistence, or multi-tenancy.
- The agent does not send campaigns — the founder retains final approval.

Python 3.10+ required.
