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

from backend.sqlite_helper import get_recent_detections, get_recent_entries, get_occupancy_counts, get_all_entries

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


# ── read digital twin & core metrics ──────────────────────────────────────────
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
        twin = {"slots": []}
except Exception as e:
    st.error(f"Error loading metrics: {e}")
    total_slots = free_slots = occupied_slots = reserved_slots = 0
    twin = {"slots": []}
    occupancy = {"entries": 0}

# ── top level dashboard tabs ──────────────────────────────────────────────────
tab_live, tab_gate, tab_logs = st.tabs(["📊 Live Overview", "🛂 Gate Management", "📋 System Logs"])

with tab_live:
    # ── top metrics ──
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Occupied Slots", occupied_slots, delta=f"{occupancy.get('entries', 0)} active entries")
    with col2:
        st.metric("Available Slots", free_slots, delta=f"out of {total_slots} total", delta_color="inverse")
    with col3:
        if total_slots > 0:
            utilisation = occupied_slots / total_slots * 100
            st.metric("Utilisation", f"{utilisation:.1f}%", delta=f"{reserved_slots} reserved" if reserved_slots > 0 else "No reservations")
        else:
            st.metric("Utilisation", "N/A")
    with col4:
        st.metric("Total Slots", total_slots)
        
    st.divider()

    # ── digital-twin live view ──
    st.subheader("🅿️ Live Parking Slot Map")
    
    slots_by_size: dict[str, list] = {"small": [], "medium": [], "large": []}
    for slot in twin.get("slots", []):
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
                            margin:5px 0;background-color:{bg}; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h4 style="margin:0;color:{text};">{emoji} Slot {slot['id']}</h4>
                    <p style="margin:5px 0;color:{text};"><b>Size:</b> {slot['size'].upper()}</p>
                    <p style="margin:5px 0;color:{text};"><b>Distance:</b> {slot['distance']} m</p>
                    <p style="margin:5px 0;color:{text};"><b>Status:</b> <strong>{status.upper()}</strong></p>
                </div>
                """, unsafe_allow_html=True)
        st.write("")

with tab_gate:
    col_gate_left, col_gate_right = st.columns([1, 1])
    
    with col_gate_left:
        # ── manual exit ──
        st.subheader("🚗 Record Manual Exit")
        with st.container(border=True):
            exit_plate = st.text_input("Licence plate to exit", placeholder="WB10AB1234").upper()
            if st.button("Record Exit", type="primary", use_container_width=True) and exit_plate:
                try:
                    resp = requests.post(
                        f"{FLASK_BASE}/exit",
                        json={"plate": exit_plate},
                        timeout=10,
                    )
                    data = resp.json()
                    if data.get("status") == "exited":
                        st.success(f"✅ Exit recorded for **{exit_plate}** (Slot {data.get('slot_id')} freed)")
                        time.sleep(1)
                        st.rerun()
                    elif data.get("status") == "not_found":
                        st.warning(f"⚠️ No active entry for **{exit_plate}**")
                    else:
                        st.error(f"Error: {data.get('message')}")
                except Exception as e:
                    st.error(f"Cannot reach backend: {e}")

        # ── upload footage ──
        st.subheader("📷 Frontgate Footage Scan")
        with st.container(border=True):
            st.write("Upload an image or video to simulate gate detection")
            uploaded_file = st.file_uploader("Choose an image/video...", type=["jpg", "jpeg", "png", "mp4", "avi", "mov"])
            if uploaded_file is not None:
                if st.button("Process Footage", type="primary", use_container_width=True):
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
                                st.success(f"✅ Plate: **{plate_detected}** (Latency: {latency:.2f}s)")
                                entry_status = data.get("status") if "entry_result" not in data else data["entry_result"].get("status")
                                if entry_status in ["granted", "completed", "entered"]:
                                    st.info(f"Status: Access Granted")
                                elif entry_status == "denied":
                                    st.error(f"Status: Access Denied")
                                else:
                                    st.warning(f"Status: {entry_status}")
                            else:
                                st.warning(f"Detection Status: {data.get('status', 'No plate detected')}")
                            with st.expander("Raw API Response"):
                                st.json(data)
                        except Exception as e:
                            st.error(f"Error processing footage: {e}")
                            
    with col_gate_right:
        # ── detections feed ──
        st.subheader("🎥 Recent Live Detections")
        try:
            detections = get_recent_detections(limit=25)
            if detections:
                df_det = pd.DataFrame([[p, format_timestamp(d)] for p, d in detections], columns=["Plate", "Detected At"])
                st.dataframe(df_det, use_container_width=True, height=500, hide_index=True)
            else:
                st.info("No detections yet")
        except Exception as e:
            st.error(f"Error loading detections: {e}")

with tab_logs:
    st.subheader("📋 Comprehensive Vehicle Logs")
    try:
        all_entries = get_all_entries()
        if all_entries:
            # plate, model, size, slot_id, price, entered_at, exited_at
            formatted_entries = []
            for e in all_entries:
                plate, model, size, slot_id, price, entered_at, exited_at = e
                status = "🟢 Active" if not exited_at else "🔴 Exited"
                formatted_entries.append({
                    "Status": status,
                    "Plate": plate,
                    "Model": model or "N/A",
                    "Size": (size or "N/A").title(),
                    "Slot": f"Slot {slot_id}" if slot_id else "N/A",
                    "Price": f"₹{price:.2f}" if price else "N/A",
                    "Entered At": format_timestamp(entered_at),
                    "Exited At": format_timestamp(exited_at) if exited_at else "-"
                })
            
            df_entries = pd.DataFrame(formatted_entries)
            
            # Simple filters
            col_f1, col_f2 = st.columns([1, 2])
            with col_f1:
                filter_status = st.selectbox("Filter Status", ["All", "🟢 Active", "🔴 Exited"])
            with col_f2:
                search_query = st.text_input("Search Plate / Model")
                
            if filter_status != "All":
                df_entries = df_entries[df_entries["Status"] == filter_status]
            if search_query:
                df_entries = df_entries[df_entries["Plate"].str.contains(search_query, case=False, na=False) | 
                                        df_entries["Model"].str.contains(search_query, case=False, na=False)]
                                        
            st.dataframe(df_entries, use_container_width=True, height=600, hide_index=True)
            
            # Download button
            csv = df_entries.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Logs as CSV", data=csv, file_name="parking_logs.csv", mime="text/csv")
            
        else:
            st.info("No system logs available yet.")
    except Exception as e:
        st.error(f"Error loading logs: {e}")

# ── global refresh ──
st.divider()
col_b1, col_b2, col_b3 = st.columns([2, 1, 2])
with col_b2:
    if st.button("🔄 Refresh Dashboard", type="primary", use_container_width=True):
        st.session_state.last_refresh_time = time.time()
        st.rerun()

st.caption("🛂 Security Control Center | Developed for Research Benchmarking & Operations")