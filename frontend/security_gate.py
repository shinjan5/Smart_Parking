"""
frontend/security_gate.py  — Security Observation Dashboard
Run:  streamlit run frontend/security_gate.py
"""
import streamlit as st
import sys, requests, json
from pathlib import Path
import pandas as pd
from datetime import datetime
import time

# FIX: resolve paths relative to THIS file so the dashboard works regardless
# of the working directory from which streamlit is launched.
THIS_DIR  = Path(__file__).resolve().parent
ROOT_DIR  = THIS_DIR.parent

sys.path.append(str(ROOT_DIR))

from backend.sqlite_helper import get_recent_detections, get_recent_entries, get_occupancy_counts

# FIX: twin path anchored to the repo root — not to cwd
TWIN_PATH = ROOT_DIR / "backend" / "mock_digital_twin.json"
FLASK_BASE = "http://localhost:5000"

st.set_page_config(
    page_title="Security Dashboard",
    page_icon="🛂",
    layout="wide",
)
st.title("🛂 Security Observation Dashboard")


def format_timestamp(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception:
        return iso_timestamp


# ── auto-refresh ─────────────────────────────────────────────────────────────
if "last_refresh_time" not in st.session_state:
    st.session_state.last_refresh_time = time.time()

auto_refresh = st.checkbox("Auto-refresh (every 5 s)", value=False)
if auto_refresh:
    time.sleep(5)
    st.session_state.last_refresh_time = time.time()
    st.rerun()

st.caption(
    f"Last updated: {time.strftime('%H:%M:%S', time.localtime(st.session_state.last_refresh_time))}"
)


# ── top metrics ───────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

try:
    occupancy = get_occupancy_counts()

    if TWIN_PATH.exists():
        with open(TWIN_PATH) as f:
            twin = json.load(f)
        total_slots    = len(twin["slots"])
        free_slots     = sum(1 for s in twin["slots"] if s["status"] == "free")
        occupied_slots = sum(1 for s in twin["slots"] if s["status"] == "occupied")
        reserved_slots = sum(1 for s in twin["slots"] if s["status"] == "reserved")
    else:
        st.warning(f"⚠️ Digital twin not found at: {TWIN_PATH}")
        total_slots = free_slots = occupied_slots = reserved_slots = 0

    with col1:
        st.metric(
            "Occupied Slots",
            occupied_slots,
            delta=f"{occupancy['entries']} active entries",
        )
    with col2:
        st.metric(
            "Available Slots",
            free_slots,
            delta=f"out of {total_slots} total",
            delta_color="inverse",
        )
    with col3:
        if total_slots > 0:
            utilisation = occupied_slots / total_slots * 100
            st.metric(
                "Utilisation",
                f"{utilisation:.1f}%",
                delta=f"{reserved_slots} reserved" if reserved_slots > 0 else "No reservations",
            )
        else:
            st.metric("Utilisation", "N/A")

except Exception as e:
    st.error(f"Error loading metrics: {e}")

st.divider()

# ── manual exit ───────────────────────────────────────────────────────────────
with st.expander("🚗 Record Manual Exit"):
    exit_plate = st.text_input("Licence plate to exit", placeholder="WB10AB1234").upper()
    if st.button("Record Exit", type="primary") and exit_plate:
        try:
            resp = requests.post(
                f"{FLASK_BASE}/exit",
                json={"plate": exit_plate},
                timeout=10,
            )
            data = resp.json()
            if data.get("status") == "exited":
                st.success(
                    f"✅ Exit recorded for **{exit_plate}** "
                    f"(Slot {data.get('slot_id')} freed in digital twin)"
                )
                st.rerun()
            elif data.get("status") == "not_found":
                st.warning(f"⚠️ No active entry for **{exit_plate}**")
            else:
                st.error(f"Error: {data.get('message')}")
        except Exception as e:
            st.error(f"Cannot reach backend: {e}")

st.divider()

# ── detections + entries ──────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🎥 Recent Detections")
    try:
        detections = get_recent_detections(limit=20)
        if detections:
            df = pd.DataFrame(
                [[p, format_timestamp(d)] for p, d in detections],
                columns=["Plate", "Detected At"],
            )
            st.dataframe(df, use_container_width=True, height=400)
        else:
            st.info("No detections yet")
    except Exception as e:
        st.error(f"Error loading detections: {e}")

with col_right:
    st.subheader("✅ Recent Entries")
    try:
        entries = get_recent_entries(limit=20)
        if entries:
            # FIX: currency symbol is ₹ (INR), not $
            df = pd.DataFrame(
                [
                    [plate, f"Slot {slot_id}", f"₹{price:.2f}", format_timestamp(entered_at)]
                    for plate, slot_id, price, entered_at in entries
                ],
                columns=["Plate", "Slot", "Price (₹)", "Entered At"],
            )
            st.dataframe(df, use_container_width=True, height=400)
        else:
            st.info("No entries yet")
    except Exception as e:
        st.error(f"Error loading entries: {e}")

st.divider()

# ── digital-twin live view ───────────────────────────────────────────────────
st.subheader("🅿️ Parking Slot Status (Live)")

try:
    if TWIN_PATH.exists():
        with open(TWIN_PATH) as f:
            twin = json.load(f)

        slots_by_size: dict[str, list] = {"small": [], "medium": [], "large": []}
        for slot in twin["slots"]:
            slots_by_size[slot["size"]].append(slot)

        for size_label, slots in slots_by_size.items():
            if not slots:
                continue
            st.markdown(f"### {size_label.upper()} Slots")
            cols = st.columns(min(len(slots), 4))

            for idx, slot in enumerate(slots):
                with cols[idx % len(cols)]:
                    status = slot["status"]
                    if status == "free":
                        emoji, color, bg, text = "🟢", "#28a745", "#d4edda", "#155724"
                    elif status == "reserved":
                        emoji, color, bg, text = "🟡", "#ffc107", "#fff3cd", "#856404"
                    else:
                        emoji, color, bg, text = "🔴", "#dc3545", "#f8d7da", "#721c24"

                    st.markdown(f"""
                    <div style="padding:15px;border-left:5px solid {color};border-radius:8px;
                                margin:5px 0;background-color:{bg};">
                        <h4 style="margin:0;color:{text};">{emoji} Slot {slot['id']}</h4>
                        <p style="margin:5px 0;color:{text};"><b>Size:</b> {slot['size'].upper()}</p>
                        <p style="margin:5px 0;color:{text};"><b>Distance:</b> {slot['distance']} m</p>
                        <p style="margin:5px 0;color:{text};"><b>Status:</b> <strong>{status.upper()}</strong></p>
                    </div>
                    """, unsafe_allow_html=True)

            st.write("")

    else:
        st.warning(f"⚠️ Digital twin not found at: {TWIN_PATH}")

except Exception as e:
    st.error(f"❌ Error loading digital twin: {e}")
    import traceback
    st.code(traceback.format_exc())

st.divider()

# ── summary statistics ────────────────────────────────────────────────────────
st.subheader("📊 Summary Statistics")

col_s1, col_s2, col_s3, col_s4 = st.columns(4)

try:
    if TWIN_PATH.exists():
        with open(TWIN_PATH) as f:
            twin = json.load(f)

        def _count(size, status=None):
            return sum(
                1 for s in twin["slots"]
                if s["size"] == size and (status is None or s["status"] == status)
            )

        col_s1.metric("Small Slots",  f"{_count('small','free')}/{_count('small')}",  delta="Free")
        col_s2.metric("Medium Slots", f"{_count('medium','free')}/{_count('medium')}", delta="Free")
        col_s3.metric("Large Slots",  f"{_count('large','free')}/{_count('large')}",  delta="Free")
        col_s4.metric("Active Vehicles", occupancy.get("entries", 0))

except Exception as e:
    st.error(f"Error loading statistics: {e}")

st.divider()

col_b1, col_b2, col_b3 = st.columns([2, 1, 2])
with col_b2:
    if st.button("🔄 Refresh Now", type="primary", use_container_width=True):
        st.session_state.last_refresh_time = time.time()
        st.rerun()

st.caption("🛂 Security Dashboard | Real-time monitoring of parking facility")