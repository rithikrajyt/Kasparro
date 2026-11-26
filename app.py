"""Streamlit UI for the Promotion Readiness Agent."""

import json
import streamlit as st
from agent import run_readiness_check

st.set_page_config(page_title="Promotion Readiness Agent", page_icon="✅", layout="wide")

# Minimal, targeted CSS — work WITH Streamlit's theme, not against it
st.markdown("""
<style>
    /* Hide default chrome for cleaner look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Tighten top padding */
    .block-container { padding-top: 2rem; }

    /* KPI tiles */
    .kpi-tile {
        border-radius: 10px;
        padding: 18px 14px;
        text-align: center;
        border: 1px solid rgba(128,128,128,0.15);
    }
    .kpi-tile h2 { margin: 0; font-size: 2.2rem; font-weight: 700; }
    .kpi-tile p  { margin: 0; font-size: 0.75rem; text-transform: uppercase;
                   letter-spacing: 0.08em; opacity: 0.6; }

    /* Status banner */
    .status-banner {
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1rem;
    }
    .status-banner h2 { margin: 0 0 2px 0; font-size: 1.6rem; }
    .status-banner p  { margin: 0; font-size: 0.85rem; opacity: 0.85; }

    .banner-ready      { background: #065f46; color: #d1fae5; border: 1px solid #34d399; }
    .banner-not-ready   { background: #7f1d1d; color: #fee2e2; border: 1px solid #f87171; }
    .banner-verify      { background: #78350f; color: #fef3c7; border: 1px solid #fbbf24; }

    /* Check items */
    .check-row {
        padding: 10px 14px;
        border-radius: 6px;
        margin-bottom: 6px;
        font-size: 0.9rem;
    }
    .check-pass       { background: rgba(16,185,129,0.08); border-left: 3px solid #34d399; }
    .check-fail       { background: rgba(239,68,68,0.08);  border-left: 3px solid #ef4444; }
    .check-unverified { background: rgba(245,158,11,0.08); border-left: 3px solid #f59e0b; }

    /* Blocker cards */
    .blocker {
        background: rgba(127,29,29,0.15);
        border: 1px solid rgba(248,113,113,0.3);
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ── Header ──────────────────────────────────────────────────
st.title("✅ Promotion Readiness Agent")
st.caption(
    "Compares the approved offer against Shopify discount settings, "
    "Klaviyo email copy, and live checkout prices — then gives a go/no-go."
)
st.divider()

# ── Controls ────────────────────────────────────────────────
REHEARSALS = {
    "A": "All pass — happy path",
    "B": "Stale pillowcase data → fresh retry finds leakage",
    "C": "Wrong discount % on eligible products (15% instead of 20%)",
    "D": "Discount leakage — excluded pillowcase gets 20% off",
    "E": "All observations stale (>10 min old), no fresh data",
    "F": "Both wrong % on eligible AND leakage on excluded",
    "G": "Missing pillowcase observation entirely",
}

col1, col2, col3 = st.columns([4, 1.5, 1])
with col1:
    question = st.text_input("Founder question", value="Are we ready to send?")
with col2:
    rehearsal = st.selectbox(
        "Rehearsal",
        options=list(REHEARSALS.keys()),
        format_func=lambda k: f"{k} — {REHEARSALS[k][:40]}",
    )
with col3:
    simulate_failure = st.checkbox("Simulate failure",
                                   help="Simulates checkout service timeout on retry")

st.caption(f"**Rehearsal {rehearsal}:** {REHEARSALS[rehearsal]}")

run = st.button("Run Readiness Check", type="primary", use_container_width=True)

if not run:
    st.info("👆 Press **Run Readiness Check** to validate the promotion.", icon="ℹ️")
    st.stop()

with st.spinner("Running checks…"):
    result = run_readiness_check(
        question=question,
        rehearsal=rehearsal,
        simulate_failure=simulate_failure,
    )

# ── Recommendation Banner ───────────────────────────────────
rec = result["recommendation"]
banner_cfg = {
    "READY":              ("banner-ready",     "All systems go — promotion is validated."),
    "NOT READY":          ("banner-not-ready",  "Blocking issues must be resolved before launch."),
    "NEEDS VERIFICATION": ("banner-verify",     "Some checks could not be verified — manual review needed."),
}
cls, subtitle = banner_cfg[rec]
st.markdown(f"""
<div class="status-banner {cls}">
    <h2>{rec}</h2>
    <p>{subtitle}</p>
</div>
""", unsafe_allow_html=True)

# ── KPI Tiles ───────────────────────────────────────────────
s = result["summary"]
k1, k2, k3, k4 = st.columns(4)
tiles = [
    (k1, s["total_checks"], "Total Checks",  "#e2e8f0"),
    (k2, s["passed"],       "Passed",         "#34d399"),
    (k3, s["failed"],       "Failed",         "#f87171"),
    (k4, s["unverified"],   "Unverified",     "#fbbf24"),
]
for col, value, label, color in tiles:
    with col:
        st.markdown(f"""
        <div class="kpi-tile">
            <p>{label}</p>
            <h2 style="color:{color}">{value}</h2>
        </div>
        """, unsafe_allow_html=True)

st.write("")  # spacer

# ── Run Details ─────────────────────────────────────────────
with st.expander("📋  Run Details"):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Run ID** · `{result['run_id']}`")
        st.markdown(f"**Offer** · `{result['offer_id']}`")
        st.markdown(f"**Rehearsal** · {result['rehearsal']}")
    with c2:
        st.markdown(f"**Evaluation started** · {result['evaluation_started_at']}")
        st.markdown(f"**Completed** · {result['run_completed_at']}")
        st.markdown(f"**Freshness threshold** · {result['freshness_threshold_minutes']} min")

# ── Checks ──────────────────────────────────────────────────
st.subheader("Checks")

pass_checks = [c for c in result["checks"] if c["status"] == "PASS"]
fail_checks = [c for c in result["checks"] if c["status"] == "FAIL"]
unv_checks  = [c for c in result["checks"] if c["status"] == "UNVERIFIED"]

tab_all, tab_pass, tab_fail, tab_unv = st.tabs([
    f"All ({len(result['checks'])})",
    f"✅ Passed ({len(pass_checks)})",
    f"❌ Failed ({len(fail_checks)})",
    f"⚠️ Unverified ({len(unv_checks)})",
])

def _render_checks(checks):
    if not checks:
        st.success("No items in this category.")
        return
    for check in checks:
        status = check["status"]
        icon = {"PASS": "✅", "FAIL": "❌", "UNVERIFIED": "⚠️"}[status]
        css = {"PASS": "check-pass", "FAIL": "check-fail", "UNVERIFIED": "check-unverified"}[status]

        with st.expander(f"{icon}  {check['name']}"):
            st.markdown(f"""
            <div class="check-row {css}">
                <strong>{check['check_id']}</strong><br>
                Expected: {check['expected']}<br>
                Actual: {check['actual']}
            </div>
            """, unsafe_allow_html=True)

            if check.get("evidence_id"):
                st.caption(f"📎 Evidence `{check['evidence_id']}` · {check.get('evidence_timestamp', '—')}")
            if check.get("explanation"):
                st.warning(check["explanation"], icon="💡")

with tab_all:
    _render_checks(result["checks"])
with tab_pass:
    _render_checks(pass_checks)
with tab_fail:
    _render_checks(fail_checks)
with tab_unv:
    _render_checks(unv_checks)

# ── Blockers ────────────────────────────────────────────────
if result["blockers"]:
    st.subheader("🚫 Blockers")
    for b in result["blockers"]:
        st.markdown(f"""
        <div class="blocker">
            <strong style="color:#f87171">[{b['owner']}]</strong> {b['description']}<br>
            <span style="opacity:0.7">→ {b['action']}</span>
        </div>
        """, unsafe_allow_html=True)

# ── Unverified Items ────────────────────────────────────────
if result["unverified_items"]:
    st.subheader("⚠️ Unverified Items")
    for u in result["unverified_items"]:
        st.warning(f"**{u.get('check_id', u.get('product_id'))}** — {u['reason']}")

# ── Activity Log ────────────────────────────────────────────
with st.expander("📝  Agent Activity Log"):
    log_lines = []
    for entry in result["activity_log"]:
        icon = "✅" if entry["result"] == "ok" else "⏱️"
        log_lines.append(
            f"{icon}  {entry['timestamp']}  │  {entry['action']}  │  {entry['detail']}  →  {entry['result']}"
        )
    st.code("\n".join(log_lines), language=None)

# ── Download & Footer ───────────────────────────────────────
st.divider()
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    st.download_button(
        "📥  Download JSON Report",
        data=json.dumps(result, indent=2, default=str),
        file_name=f"readiness_{result['run_id']}.json",
        mime="application/json",
        use_container_width=True,
    )

st.info("🔒 **The agent does not send the campaign.** The founder retains final approval.", icon="🔒")
