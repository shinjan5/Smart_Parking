"""
frontend/app.py — Unified Smart Parking Application
Run: streamlit run frontend/app.py
"""
import streamlit as st
import sys, requests, json
from pathlib import Path
import pandas as pd
from datetime import datetime
import time
import pytz

# Resolve backend package
THIS_DIR = Path(__file__).resolve().parent
ROOT_DIR = THIS_DIR.parent
sys.path.append(str(ROOT_DIR))

from backend.sqlite_helper import (
    create_booking,
    get_booking_by_plate,
    get_recent_entries,
    get_recent_detections,
    get_entry_by_plate,
    get_occupancy_counts,
    get_all_entries,
    get_conn,
)

TWIN_PATH = ROOT_DIR / "backend" / "mock_digital_twin.json"
FLASK_BASE = "http://localhost:5000"

st.set_page_config(
    page_title="Smart Parking System",
    layout="wide",
)

st.sidebar.title("Navigation")
route = st.sidebar.radio("Select View:", ["Customer Portal", "Control Center"])
st.sidebar.markdown("---")

# Shared Helpers
def format_timestamp_local(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        tz = pytz.timezone("Asia/Kolkata")
        if dt.tzinfo is None:
            dt_local = dt.replace(tzinfo=pytz.UTC).astimezone(tz)
        else:
            dt_local = dt.astimezone(tz)
        return dt_local.strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception:
        return iso_timestamp

def format_timestamp(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_timestamp

def check_system_status():
    try:
        resp = requests.get(f"{FLASK_BASE}/", timeout=2)
        return "Online", "#28a745"
    except Exception:
        return "Offline", "#6c757d"

def count_detections_for_plate(plate: str) -> int:
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM detections WHERE plate=?", (plate,))
    count = cur.fetchone()[0]
    conn.close()
    return count

if route == "Customer Portal":
    st.title("🚗 Smart Parking — Customer Portal")

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
            plate = st.text_input("Licence Plate Number *", max_chars=20, placeholder="e.g., WB10AB1234").upper()
            
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
            lookup_plate = st.text_input("Enter Licence Plate", key="lookup", placeholder="WB10AB1234").upper()
            search_btn = st.button("🔎 Search", type="primary", use_container_width=True)

            st.divider()
            st.caption("Already parked? Record your exit:")
            exit_plate = st.text_input("Plate to exit", key="exit_plate", placeholder="WB10AB1234").upper()
            if st.button("🚗 Record Exit", use_container_width=True) and exit_plate:
                try:
                    resp = requests.post(f"{FLASK_BASE}/exit", json={"plate": exit_plate}, timeout=10)
                    data = resp.json()
                    if data.get("status") == "exited":
                        st.success(f"✅ Exit recorded for **{exit_plate}** (Slot {data.get('slot_id')} freed)")
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
                        with col_a: st.metric("Model", booking.get("model", "N/A"))
                        with col_b: st.metric("Size", booking.get("size", "N/A"))
                        with col_c:
                            if booking.get("status", "pending") == "entered":
                                st.metric("Status", "✅ Entered", delta="Active")
                            else:
                                st.metric("Status", "⏳ Pending", delta="Awaiting")

                        entry = get_entry_by_plate(lookup_plate)
                        if entry:
                            st.success("🎉 **Vehicle has entered parking!**")
                            st.write(f"- **Slot:** {entry['slot_id']}")
                            st.write(f"- **Price:** ₹{entry['price']}")
                            st.write(f"- **Entry Time:** {format_timestamp_local(entry['entered_at'])}")
                        else:
                            st.info("⏳ Vehicle not yet entered. Proceed to gate.")
                            detection_count = count_detections_for_plate(lookup_plate)
                            if detection_count > 0:
                                st.warning(f"📸 Your plate has been detected {detection_count} time(s) — entry is processing…")
                    else:
                        st.warning(f"⚠️ No booking found for **{lookup_plate}**")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
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
                formatted = [[plate, slot_id, f"₹{price:.2f}", format_timestamp_local(entered_at)] for plate, slot_id, price, entered_at in entries]
                df = pd.DataFrame(formatted, columns=["Plate", "Slot ID", "Price (₹)", "Entered At"])
                most_recent = df.iloc[0]
                st.info(f"🎉 **Latest Arrival:** Vehicle **{most_recent['Plate']}** parked in Slot **{most_recent['Slot ID']}**.")
                st.dataframe(df, use_container_width=True, height=350, hide_index=True)
            else:
                st.info("No entries yet.")
        except Exception as e:
            st.error(f"Error loading entries: {e}")

        st.divider()
        st.subheader("🎥 Recent Plate Detections")
        try:
            detections = get_recent_detections(limit=10)
            if detections:
                formatted_det = [[plate, format_timestamp_local(detected_at)] for plate, detected_at in detections]
                df_det = pd.DataFrame(formatted_det, columns=["Plate", "Detected At"])
                st.dataframe(df_det, use_container_width=True, height=250, hide_index=True)
            else:
                st.info("No detections yet.")
        except Exception as e:
            st.error(f"Error loading detections: {e}")

    # ══ TAB 4: GATE SIMULATION ═══════════════════════════════════════════════════
    with tab4:
        st.header("🛂 Simulate Gate Entry")
        st.info("Upload an image or video to simulate a vehicle arriving at the gate. The AI pipeline will process it.")
        with st.container(border=True):
            uploaded_file = st.file_uploader("Choose an image or video...", type=["jpg", "jpeg", "png", "mp4", "avi", "mov"], key="cp_upload")
            if uploaded_file is not None:
                if st.button("Process Footage", type="primary", use_container_width=True, key="cp_btn"):
                    with st.spinner("Processing footage via Agentic Pipeline..."):
                        try:
                            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                            endpoint = f"{FLASK_BASE}/process-video" if uploaded_file.name.lower().endswith(("mp4", "avi", "mov")) else f"{FLASK_BASE}/vision/detect_plate"
                            start_time = time.time()
                            resp = requests.post(endpoint, files=files, timeout=120)
                            latency = time.time() - start_time
                            data = resp.json()
                            plate_detected = data.get("plate") or (data.get("entry_result", {}).get("plate"))
                            if plate_detected:
                                st.success(f"✅ Extracted Plate: **{plate_detected}** (Latency: {latency:.2f}s)")
                                entry_status = data.get("status")
                                if "entry_result" in data: entry_status = data["entry_result"].get("status")
                                if entry_status in ["granted", "completed", "entered"]: st.info(f"Entry Status: Allowed / Granted")
                                elif entry_status == "denied": st.error(f"Entry Status: Denied")
                                else: st.warning(f"Entry Status: {entry_status}")
                            else:
                                st.warning(f"Detection Status: {data.get('status', 'No plate detected')}")
                            with st.expander("Raw API Response"):
                                st.json(data)
                        except Exception as e:
                            st.error(f"Error processing footage: {e}")

    st.divider()
    st.caption("🚗 Smart Parking System | Customer Portal")

elif route == "Control Center":
    st.title("Smart Parking Control Center")
    st.markdown("---")

    sys_status, sys_color = check_system_status()

    if "last_refresh_time" not in st.session_state:
        st.session_state.last_refresh_time = time.time()

    col_status, col_refresh = st.columns([8, 2])
    with col_status:
        st.markdown(f"**System Status:** <span style='color:{sys_color}; font-weight:bold;'>{sys_status}</span> | **Last Updated:** {time.strftime('%H:%M:%S', time.localtime(st.session_state.last_refresh_time))}", unsafe_allow_html=True)
    with col_refresh:
        if st.button("Refresh Dashboard", use_container_width=True, key="cc_refresh"):
            st.session_state.last_refresh_time = time.time()
            st.rerun()

    twin = {"slots": []}
    alerts = []
    try:
        if TWIN_PATH.exists():
            with open(TWIN_PATH) as f:
                twin_data = json.load(f)
                if "slots" in twin_data: twin["slots"] = twin_data["slots"]
                else: alerts.append("Invalid JSON: 'slots' key missing in digital twin.")
        else: alerts.append("File Error: Digital twin JSON not found.")
    except json.JSONDecodeError: alerts.append("JSON Error: Failed to parse digital twin data.")
    except Exception as e: alerts.append(f"System Error: {str(e)}")

    total_slots = len(twin["slots"])
    free_slots = sum(1 for s in twin["slots"] if s.get("status") == "free")
    occupied_slots = sum(1 for s in twin["slots"] if s.get("status") == "occupied")
    reserved_slots = sum(1 for s in twin["slots"] if s.get("status") == "reserved")

    if total_slots > 0 and free_slots == 0:
        alerts.append("Warning: Parking is currently FULL.")

    st.subheader("System Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Parking Slots", total_slots)
    col2.metric("Available Slots", free_slots)
    col3.metric("Occupied Slots", occupied_slots)
    col4.metric("Reserved Slots", reserved_slots)
    st.markdown("---")

    tab_live, tab_gate, tab_logs, tab_stats = st.tabs(["Live Parking Status", "Gate Operations & Model Output", "Logs & History", "Research Statistics"])

    with tab_live:
        st.markdown("### Alerts Panel")
        if alerts:
            for alert in alerts: st.error(alert)
        elif sys_status == "Offline": st.error("Network Issue: Cannot reach backend API.")
        else: st.success("System Normal: No active alerts.")
            
        st.markdown("### Slot Layout Grid")
        if not twin["slots"]: st.info("No slot data available.")
        else:
            slots_by_size = {"small": [], "medium": [], "large": []}
            for slot in twin["slots"]:
                size = slot.get("size", "unknown")
                if size in slots_by_size: slots_by_size[size].append(slot)
                else: slots_by_size["unknown"] = slots_by_size.get("unknown", []) + [slot]
            
            for size_label, slots in slots_by_size.items():
                if not slots: continue
                st.markdown(f"**Size: {size_label.title()}**")
                cols = st.columns(min(len(slots), 6))
                for idx, slot in enumerate(slots):
                    with cols[idx % len(cols)]:
                        status = slot.get("status", "unknown")
                        if status == "free": color, bg, text = "#28a745", "#d4edda", "#155724"
                        elif status == "occupied": color, bg, text = "#dc3545", "#f8d7da", "#721c24"
                        elif status == "reserved": color, bg, text = "#ffc107", "#fff3cd", "#856404"
                        else: color, bg, text = "#6c757d", "#e2e3e5", "#383d41"

                        slot_id = slot.get('id', 'N/A')
                        distance = slot.get('distance', 'N/A')
                        
                        st.markdown(f'''
                        <div style="border: 1px solid {color}; border-top: 4px solid {color}; background-color: {bg}; color: {text}; padding: 10px; border-radius: 4px; margin-bottom: 10px; text-align: center; font-family: sans-serif;">
                            <div style="font-weight: bold; font-size: 1.1em; margin-bottom: 5px;">Slot {slot_id}</div>
                            <div style="font-size: 0.9em; text-transform: uppercase;">{status}</div>
                            <div style="font-size: 0.8em; margin-top: 5px;">Dist: {distance}m</div>
                        </div>
                        ''', unsafe_allow_html=True)

    with tab_gate:
        col_upload, col_model = st.columns([1, 1])
        with col_upload:
            st.markdown("### Manual Gate Control")
            with st.container(border=True):
                exit_plate = st.text_input("Licence Plate to Exit", placeholder="WB10AB1234").upper()
                if st.button("Record Exit", use_container_width=True, key="cc_exit") and exit_plate:
                    try:
                        resp = requests.post(f"{FLASK_BASE}/exit", json={"plate": exit_plate}, timeout=10)
                        data = resp.json()
                        if data.get("status") == "exited": st.success(f"Exit recorded for {exit_plate} (Slot {data.get('slot_id')} freed)")
                        elif data.get("status") == "not_found": st.warning(f"No active entry for {exit_plate}")
                        else: st.error(f"Error: {data.get('message')}")
                    except Exception as e:
                        st.error(f"Backend unreachable: {e}")

            st.markdown("### Simulate Camera Feed")
            with st.container(border=True):
                uploaded_file = st.file_uploader("Upload Image/Video File", type=["jpg", "jpeg", "png", "mp4", "avi", "mov"], key="cc_upload")
                if uploaded_file is not None:
                    if st.button("Process Footage", use_container_width=True, key="cc_process"):
                        with st.spinner("Processing..."):
                            try:
                                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                                endpoint = f"{FLASK_BASE}/process-video" if uploaded_file.name.lower().endswith(("mp4", "avi", "mov")) else f"{FLASK_BASE}/vision/detect_plate"
                                start_time = time.time()
                                resp = requests.post(endpoint, files=files, timeout=120)
                                latency = time.time() - start_time
                                try:
                                    data = resp.json()
                                    st.session_state.last_model_output = data
                                    st.session_state.last_model_latency = latency
                                except json.JSONDecodeError: st.error("Invalid JSON response from server.")
                            except Exception as e: st.error(f"Network error processing footage: {e}")
                                
        with col_model:
            st.markdown("### Model Output Panel")
            if "last_model_output" in st.session_state:
                data = st.session_state.last_model_output
                latency = st.session_state.last_model_latency
                plate_detected = data.get("plate") or (data.get("entry_result", {}).get("plate"))
                conf = data.get("confidence", data.get("entry_result", {}).get("confidence", "N/A"))
                
                st.markdown(f"**Processing Time:** {latency:.3f} s")
                if conf != "N/A": st.markdown(f"**Detection Confidence:** {conf if isinstance(conf, str) else f'{conf:.2%}'}")
                else: st.markdown("**Detection Confidence:** N/A")
                    
                if plate_detected: st.success(f"Object Detected: {plate_detected}")
                else: st.warning("Detection Status: No object detected")
                    
                st.markdown("**Native JSON Response:**")
                st.json(data)
            else:
                st.info("No model output generated yet. Upload footage to begin.")

    with tab_logs:
        st.markdown("### Event History")
        try:
            all_entries = get_all_entries()
            if all_entries:
                formatted_entries = []
                for e in all_entries:
                    plate, model, size, slot_id, price, entered_at, exited_at = e
                    status = "Active" if not exited_at else "Exited"
                    formatted_entries.append({"Timestamp": format_timestamp(entered_at), "Event Type": "Entry", "Plate": plate, "Slot": str(slot_id) if slot_id else "N/A", "Status": status})
                df_entries = pd.DataFrame(formatted_entries)
                st.dataframe(df_entries, use_container_width=True, hide_index=True)
                csv = df_entries.to_csv(index=False).encode('utf-8')
                st.download_button("Download CSV", data=csv, file_name="logs.csv", mime="text/csv")
            else:
                st.info("No historical logs found.")
        except Exception as e:
            st.error(f"Failed to load logs: {e}")

    with tab_stats:
        st.markdown("### Evaluation Metrics")
        
        STATS_PATH = ROOT_DIR / "backend" / "research_stats.json"
        if STATS_PATH.exists():
            with open(STATS_PATH) as f:
                stats = json.load(f)
            
            st.markdown(f"**Last Benchmark Run:** {stats.get('timestamp', 'N/A')}")
            
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.markdown("**Model Performance**")
                perf_data = {
                    "Metric": ["Accuracy", "Precision", "Recall", "F1-score"],
                    "Value": [
                        f"{stats.get('accuracy', 0):.1f}%",
                        f"{stats.get('precision', 0):.1f}%",
                        f"{stats.get('recall', 0):.1f}%",
                        f"{stats.get('f1_score', 0):.1f}%"
                    ]
                }
                st.dataframe(pd.DataFrame(perf_data), hide_index=True, use_container_width=True)
            
            with col_s2:
                st.markdown("**System Efficiency**")
                eff_data = {
                    "Metric": ["Avg Latency", "Avg Steps", "Tested Samples", "False Positives", "False Negatives"],
                    "Value": [
                        f"{stats.get('avg_latency_ms', 0):.0f} ms",
                        f"{stats.get('avg_steps', 0):.1f}",
                        str(stats.get('total_samples', 0)),
                        str(stats.get('false_positives', 0)),
                        str(stats.get('false_negatives', 0))
                    ]
                }
                st.dataframe(pd.DataFrame(eff_data), hide_index=True, use_container_width=True)
                
            st.markdown("---")
            st.markdown("**Confusion Matrix Distribution**")
            # Calculate values for chart
            tp = stats.get("successful_executions", 0) - stats.get("false_positives", 0)
            fp = stats.get("false_positives", 0)
            fn = stats.get("false_negatives", 0)
            
            chart_df = pd.DataFrame({
                "Category": ["True Positives", "False Positives", "False Negatives"],
                "Count": [tp, fp, fn]
            }).set_index("Category")
            st.bar_chart(chart_df)
        else:
            st.warning("No benchmark data found. Please run the research benchmark script to generate stats.")
