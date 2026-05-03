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
tab1, tab2, tab3, tab4 = st.tabs(["📋 Pre-Booking", "🔍 Check Status", "📊 Entry Dashboard", "🛂 Gate Simulation"])


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

    import csv
    from pathlib import Path
    import os

    vehicle_data = {}
    csv_path = Path("test_data/VehicleData")
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                model_name = row.get("Vehicle Model", "").strip()
                if model_name:
                    vehicle_data[model_name] = {
                        "Category": row.get("Category", "").strip(),
                        "Vehicle Size": row.get("Vehicle Size", "").strip()
                    }
    vehicle_data["Other (Specify)"] = {"Category": "Hatchback", "Vehicle Size": "Small"}

    col_a, col_b = st.columns(2)
    with col_a:
        name = st.text_input("Full Name *", placeholder="e.g., John Doe")
        plate = st.text_input("Licence Plate Number *", max_chars=20, placeholder="e.g., WB10AB1234", help="Enter your licence plate (alphanumeric only)").upper()
        
        # Load models
        model_options = list(vehicle_data.keys())
        selected_model = st.selectbox("Car Model *", model_options)
        
        if selected_model == "Other (Specify)":
            model = st.text_input("Specify Car Model *")
        else:
            model = selected_model
    
    with col_b:
        if selected_model == "Other (Specify)":
            brand = st.text_input("Brand *")
            all_cats = list(set(v["Category"] for v in vehicle_data.values() if v["Category"]))
            if not all_cats: all_cats = ["Hatchback", "Sedan", "SUV", "Two Wheeler"]
            category = st.selectbox("Vehicle Category *", sorted(all_cats))
            size = st.selectbox("Vehicle Size *", ["Small", "Medium", "Large"])
        else:
            car_info = vehicle_data[selected_model]
            guess_brand = model.split(" ")[0]
            if model.startswith("Maruti Suzuki"): guess_brand = "Maruti Suzuki"
            elif model.startswith("Royal Enfield"): guess_brand = "Royal Enfield"
            elif model.startswith("Land Rover"): guess_brand = "Land Rover"
            elif model.startswith("Mercedes-Benz"): guess_brand = "Mercedes-Benz"
            
            brand = st.text_input("Brand *", value=guess_brand)
            category = st.text_input("Vehicle Category *", value=car_info["Category"], disabled=True)
            size = st.text_input("Vehicle Size *", value=car_info["Vehicle Size"], disabled=True)
            
        fuel_type = st.selectbox("Fuel Type *", ["Petrol", "Diesel", "EV", "Hybrid"])

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        entry_time = st.time_input("Expected Entry Time *")
    with col_t2:
        exit_time = st.time_input("Expected Exit Time *")
    
    available_prefs = ["Near Elevator", "Near Stairs", "Covered"]
    if fuel_type in ["EV", "Hybrid"]:
        available_prefs.append("EV Charging Dock")
    preferences = st.multiselect("Preferences", available_prefs)

    submit = st.button("🎫 Create Pre-Booking", type="primary", use_container_width=True)

    if submit:
        if not name or not plate or not model or not brand:
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
                    prefs_str = ", ".join(preferences)
                    # For sqlite, size must be lowercase
                    db_size = size.lower()
                    create_booking(plate, name, brand, model, category, db_size, str(entry_time), str(exit_time), prefs_str, fuel_type)
                    st.success("✅ Pre-booking created successfully!")
                    st.balloons()
                    
                    # Allocate slot and get price
                    with st.spinner("Allocating slot & calculating price..."):
                        import requests
                        try:
                            resp = requests.post("http://localhost:5000/prebook/allocate", json={
                                "plate": plate,
                                "size": db_size,
                                "preferences": prefs_str
                            }, timeout=180)
                            data = resp.json()
                            if data.get("status") == "success":
                                slot_msg = f"**{data.get('slot_id')}**"
                                price_val = data.get('price', {}).get('price', 'N/A')
                                price_msg = f"**₹{price_val} / hr**"
                            else:
                                slot_msg = "Pending (No slot found)"
                                price_msg = "N/A"
                        except Exception:
                            slot_msg = "Pending Allocation"
                            price_msg = "TBD"

                    st.info(f"""
                    **Booking Confirmed:**
                    - Name: **{name}**
                    - Plate: **{plate}**
                    - Vehicle: **{brand} {model}** ({category} - {size})
                    - Fuel: **{fuel_type}**
                    - Preferences: **{prefs_str}**
                    - Allocated Slot: {slot_msg}
                    - Dynamic Price Estimate: {price_msg}

                    Drive to the gate — the system will handle the rest!
                    """)
                    time.sleep(4)
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
                [plate, slot_id, f"₹{price:.2f}", format_timestamp(entered_at)]
                for plate, slot_id, price, entered_at in entries
            ]
            df = pd.DataFrame(formatted, columns=["Plate", "Slot ID", "Price (₹)", "Entered At"])
            
            # Show a detailed metric for the most recent entry
            most_recent = df.iloc[0]
            st.info(f"🎉 **Latest Arrival:** Vehicle **{most_recent['Plate']}** parked in Slot **{most_recent['Slot ID']}**.")
            
            st.dataframe(df, use_container_width=True, height=350, hide_index=True)
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
            st.dataframe(df_det, use_container_width=True, height=250, hide_index=True)
        else:
            st.info("No detections yet.")
    except Exception as e:
        st.error(f"Error loading detections: {e}")


# ══ TAB 4: GATE SIMULATION ═══════════════════════════════════════════════════
with tab4:
    st.header("🛂 Simulate Gate Entry")
    
    st.info("""
    **How Vehicle Entry Works:**
    1. **Camera Feed:** A camera at the physical gate captures an image or video of an arriving vehicle.
    2. **Vision Agent:** The backend processes the footage using a YOLO object detection model and OCR to extract the vehicle's licence plate.
    3. **Agentic Pipeline (LangGraph):** The system passes the plate to a multi-agent workflow:
       - **Reservation Agent:** Verifies if a pre-booking exists.
       - **Slot Allocation Agent:** Finds the nearest available slot matching the vehicle's size.
       - **Pricing Agent:** Computes dynamic pricing based on distance and demand.
       - **Persistence Agent:** Updates the database and digital twin.
    4. **Admission:** The gate opens, and the user's portal status updates to 'Entered'.
    """)
    
    st.subheader("📷 Upload Frontgate Footage")
    with st.container(border=True):
        st.write("Upload an image or video to simulate gate detection")
        uploaded_file = st.file_uploader("Choose an image or video...", type=["jpg", "jpeg", "png", "mp4", "avi", "mov"])
        
        if uploaded_file is not None:
            if st.button("Process Footage", type="primary", use_container_width=True):
                with st.spinner("Processing footage via Agentic Pipeline..."):
                    try:
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        
                        if uploaded_file.name.lower().endswith(("mp4", "avi", "mov")):
                            endpoint = f"{FLASK_BASE}/process-video"
                        else:
                            endpoint = f"{FLASK_BASE}/vision/detect_plate"
                            
                        start_time = time.time()
                        resp = requests.post(endpoint, files=files, timeout=120)
                        latency = time.time() - start_time
                        data = resp.json()
                        
                        # Fetch and check status logic
                        plate_detected = data.get("plate") or (data.get("entry_result", {}).get("plate"))
                        if plate_detected:
                            st.success(f"✅ Extracted Plate: **{plate_detected}** (Latency: {latency:.2f}s)")
                            
                            entry_status = data.get("status")
                            if "entry_result" in data:
                                entry_status = data["entry_result"].get("status")
                            
                            if entry_status in ["granted", "completed", "entered"]:
                                st.info(f"Entry Status: Allowed / Granted")
                            elif entry_status == "denied":
                                st.error(f"Entry Status: Denied")
                            else:
                                st.warning(f"Entry Status: {entry_status}")
                        else:
                            st.warning(f"Detection Status: {data.get('status', 'No plate detected')}")
                            
                        with st.expander("Raw API Response"):
                            st.json(data)
                    except Exception as e:
                        st.error(f"Error processing footage: {e}")

# ── footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("🚗 Smart Parking System | Pre-booking required | Camera-based automatic recognition")