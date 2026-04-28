"""
frontend/frontend.py  — Smart Parking Customer Portal
Run:  streamlit run frontend/frontend.py
"""
import streamlit as st
import sys, requests
from pathlib import Path
import pandas as pd
import time
from datetime import datetime
import pytz

# Resolve backend package regardless of launch directory
sys.path.append(str(Path(__file__).parent.parent))

from backend.sqlite_helper import (
    create_booking,
    get_booking_by_plate,
    get_recent_entries,
    get_recent_detections,
    get_entry_by_plate,
    get_conn,           # FIX: imported at top, not inside a conditional block
)

FLASK_BASE = "http://localhost:5000"

st.set_page_config(
    page_title="Smart Parking — Customer Portal",
    page_icon="🚗",
    layout="wide",
)
st.title("🚗 Smart Parking — Customer Portal")

# ── sidebar auto-refresh ──────────────────────────────────────────────────────
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh Entry Status", value=False)
if auto_refresh:
    refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 3, 30, 5)
    time.sleep(refresh_interval)
    st.session_state.last_refresh = time.time()
    st.rerun()

st.sidebar.caption(
    f"Last updated: {time.strftime('%H:%M:%S', time.localtime(st.session_state.last_refresh))}"
)


# ── helpers ───────────────────────────────────────────────────────────────────

def format_timestamp(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        tz = pytz.timezone("Asia/Kolkata")
        dt_local = dt.replace(tzinfo=pytz.UTC).astimezone(tz)
        return dt_local.strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception:
        return iso_timestamp


def count_detections_for_plate(plate: str) -> int:
    """Count how many times a plate has been seen by the gate camera."""
    # FIX: get_conn is now imported at the top of the file — no mid-handler import
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM detections WHERE plate=?", (plate,))
    count = cur.fetchone()[0]
    conn.close()
    return count


# ── tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📋 Pre-Booking", "🔍 Check Status", "📊 Entry Dashboard"])


# ══ TAB 1: PRE-BOOKING ═══════════════════════════════════════════════════════
with tab1:
    st.header("📋 Pre-Book Your Parking Spot")

    st.info("""
    **How it works:**
    1. Enter your vehicle details below
    2. Drive to the gate when ready
    3. Our cameras automatically detect your licence plate
    4. AI assigns you the optimal parking slot
    5. Park in your assigned spot — no manual check-in needed!
    """)

    with st.form("booking_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            plate = st.text_input(
                "Licence Plate Number *",
                max_chars=20,
                placeholder="e.g., WB10AB1234",
                help="Enter your licence plate (alphanumeric only)",
            ).upper()

            model = st.text_input(
                "Car Model *",
                placeholder="e.g., Honda City",
                help="Enter your vehicle model",
            )

        with col2:
            size = st.selectbox(
                "Vehicle Size *",
                ["small", "medium", "large"],
                help="Select your vehicle size for optimal slot allocation",
            )

        submit = st.form_submit_button(
            "🎫 Create Pre-Booking", type="primary", use_container_width=True
        )

        if submit:
            if not plate or not model:
                st.error("❌ Please fill in all required fields")
            elif len(plate) < 4:
                st.error("❌ Licence plate must be at least 4 characters")
            else:
                try:
                    existing = get_booking_by_plate(plate)
                    if existing:
                        st.warning(f"⚠️ A booking already exists for **{plate}**")
                        st.json(existing)
                    else:
                        create_booking(plate, model, size)
                        st.success("✅ Pre-booking created successfully!")
                        st.balloons()
                        st.info(f"""
                        **Booking Confirmed:**
                        - Plate: **{plate}**
                        - Vehicle: **{model}** ({size})
                        - Status: **Awaiting entry**

                        Drive to the gate — the system will handle the rest!
                        """)
                        time.sleep(1)
                        st.rerun()

                except Exception as e:
                    st.error(f"❌ Error creating booking: {e}")


# ══ TAB 2: CHECK STATUS ══════════════════════════════════════════════════════
with tab2:
    st.header("🔍 Check Booking & Entry Status")

    col_search, col_result = st.columns([1, 2])

    with col_search:
        lookup_plate = st.text_input(
            "Enter Licence Plate",
            key="lookup",
            placeholder="WB10AB1234",
        ).upper()

        search_btn = st.button("🔎 Search", type="primary", use_container_width=True)

        # ── Exit button ────────────────────────────────────────────────────
        st.divider()
        st.caption("Already parked? Record your exit:")
        exit_plate = st.text_input(
            "Plate to exit",
            key="exit_plate",
            placeholder="WB10AB1234",
        ).upper()

        if st.button("🚗 Record Exit", use_container_width=True) and exit_plate:
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
                        f"(Slot {data.get('slot_id')} freed)"
                    )
                elif data.get("status") == "not_found":
                    st.warning(f"⚠️ No active entry found for **{exit_plate}**")
                else:
                    st.error(f"Error: {data.get('message')}")
            except Exception as e:
                st.error(f"Could not reach backend: {e}")

    with col_result:
        if search_btn and lookup_plate:
            try:
                booking = get_booking_by_plate(lookup_plate)

                if booking:
                    st.success(f"✅ Booking found for **{lookup_plate}**")

                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Model", booking.get("model", "N/A"))
                    with col_b:
                        st.metric("Size", booking.get("size", "N/A"))
                    with col_c:
                        booking_status = booking.get("status", "pending")
                        if booking_status == "entered":
                            st.metric("Status", "✅ Entered", delta="Active")
                        else:
                            st.metric("Status", "⏳ Pending", delta="Awaiting")

                    entry = get_entry_by_plate(lookup_plate)

                    if entry:
                        st.success("🎉 **Vehicle has entered parking!**")
                        # FIX: currency is ₹ (INR), not $
                        st.write(f"- **Slot:** {entry['slot_id']}")
                        st.write(f"- **Price:** ₹{entry['price']}")
                        st.write(f"- **Entry Time:** {format_timestamp(entry['entered_at'])}")

                        st.markdown(f"""
                        <div style="background-color:#d4edda;padding:20px;border-radius:10px;
                                    border-left:5px solid #28a745;">
                            <h3 style="color:#155724;margin:0;">✅ Entry Confirmed</h3>
                            <p style="color:#155724;margin-top:10px;">
                                Vehicle <strong>{lookup_plate}</strong> is parked in
                                <strong>Slot {entry['slot_id']}</strong>
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                    else:
                        st.info("⏳ Vehicle not yet entered. Proceed to gate.")

                        # FIX: use the imported get_conn helper — no runtime import
                        detection_count = count_detections_for_plate(lookup_plate)
                        if detection_count > 0:
                            st.warning(
                                f"📸 Your plate has been detected {detection_count} "
                                f"time(s) — entry is processing…"
                            )
                            st.info(
                                "💡 Try refreshing in a few seconds or enable "
                                "auto-refresh in the sidebar."
                            )

                else:
                    st.warning(f"⚠️ No booking found for **{lookup_plate}**")
                    st.info("Please create a pre-booking first in the Pre-Booking tab.")

            except Exception as e:
                st.error(f"❌ Error: {e}")
                import traceback
                st.code(traceback.format_exc())

        elif search_btn:
            st.warning("Please enter a licence plate number.")


# ══ TAB 3: ENTRY DASHBOARD ═══════════════════════════════════════════════════
with tab3:
    st.header("📊 Recent Entry Activity")

    col_refresh = st.columns([4, 1])
    with col_refresh[1]:
        if st.button("🔄 Refresh", use_container_width=True):
            st.session_state.last_refresh = time.time()
            st.rerun()

    st.subheader("✅ Recent Entries")
    try:
        entries = get_recent_entries(limit=15)
        if entries:
            formatted = [
                [plate, slot_id, f"₹{price:.2f}", format_timestamp(entered_at)]   # FIX: ₹ not $
                for plate, slot_id, price, entered_at in entries
            ]
            df = pd.DataFrame(formatted, columns=["Plate", "Slot ID", "Price (₹)", "Entered At"])
            if len(df) > 0:
                st.success(
                    f"Latest: **{df.iloc[0]['Plate']}** → "
                    f"Slot **{df.iloc[0]['Slot ID']}** | {df.iloc[0]['Price (₹)']}"
                )
            st.dataframe(df, use_container_width=True, height=300)
        else:
            st.info("No entries yet. Vehicles appear here after entering through the gate.")
    except Exception as e:
        st.error(f"Error loading entries: {e}")

    st.divider()

    st.subheader("🎥 Recent Plate Detections")
    try:
        detections = get_recent_detections(limit=10)
        if detections:
            formatted_det = [
                [plate, format_timestamp(detected_at)]
                for plate, detected_at in detections
            ]
            df_det = pd.DataFrame(formatted_det, columns=["Plate", "Detected At"])
            st.dataframe(df_det, use_container_width=True, height=200)
        else:
            st.info("No detections yet.")
    except Exception as e:
        st.error(f"Error loading detections: {e}")


# ── footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("🚗 Smart Parking System | Pre-booking required | Camera-based automatic recognition")