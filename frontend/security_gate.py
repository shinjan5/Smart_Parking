import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
import time

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from backend.sqlite_helper import get_recent_detections, get_recent_entries, get_occupancy_counts
import json

st.set_page_config(page_title="Security Dashboard", page_icon="🛂", layout="wide")

st.title("🛂 Security Observation Dashboard")


def format_timestamp(iso_timestamp):
    """Convert ISO timestamp to readable format"""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%Y-%m-%d %I:%M:%S %p")  # e.g., "2025-12-26 08:18:54 AM"
    except:
        return iso_timestamp


# Auto-refresh
if "last_refresh_time" not in st.session_state:
    st.session_state.last_refresh_time = time.time()

auto_refresh = st.checkbox("Auto-refresh (every 5s)", value=False)

if auto_refresh:
    time.sleep(5)
    st.session_state.last_refresh_time = time.time()
    st.rerun()

st.caption(f"Last updated: {time.strftime('%H:%M:%S', time.localtime(st.session_state.last_refresh_time))}")

# Metrics
col1, col2, col3 = st.columns(3)

try:
    occupancy = get_occupancy_counts()
    
    # Load digital twin for total slots
    twin_path = Path(__file__).parent.parent / "backend" / "mock_digital_twin.json"
    
    if twin_path.exists():
        with open(twin_path) as f:
            twin = json.load(f)
            total_slots = len(twin["slots"])
            free_slots = sum(1 for s in twin["slots"] if s["status"] == "free")
            occupied_slots = sum(1 for s in twin["slots"] if s["status"] == "occupied")
            reserved_slots = sum(1 for s in twin["slots"] if s["status"] == "reserved")
    else:
        total_slots = 0
        free_slots = 0
        occupied_slots = 0
        reserved_slots = 0
    
    with col1:
        st.metric(
            "Occupied Slots", 
            occupied_slots,
            delta=f"{occupancy['entries']} active entries",
            delta_color="normal"
        )
    
    with col2:
        st.metric(
            "Available Slots", 
            free_slots,
            delta=f"out of {total_slots} total",
            delta_color="inverse"
        )
    
    with col3:
        if total_slots > 0:
            utilization = (occupied_slots / total_slots * 100)
            st.metric(
                "Utilization", 
                f"{utilization:.1f}%",
                delta=f"{reserved_slots} reserved" if reserved_slots > 0 else "No reservations"
            )
        else:
            st.metric("Utilization", "N/A")

except Exception as e:
    st.error(f"Error loading metrics: {e}")

st.divider()

# Two columns for detections and entries
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🎥 Recent Detections")
    try:
        detections = get_recent_detections(limit=20)
        
        if detections:
            # Format timestamps
            formatted_detections = []
            for plate, detected_at in detections:
                formatted_detections.append([
                    plate,
                    format_timestamp(detected_at)
                ])
            
            df = pd.DataFrame(formatted_detections, columns=["Plate", "Detected At"])
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
            # Format timestamps and prices
            formatted_entries = []
            for plate, slot_id, price, entered_at in entries:
                formatted_entries.append([
                    plate,
                    f"Slot {slot_id}",
                    f"${price:.2f}",
                    format_timestamp(entered_at)
                ])
            
            df = pd.DataFrame(formatted_entries, columns=["Plate", "Slot", "Price", "Entered At"])
            st.dataframe(df, use_container_width=True, height=400)
        else:
            st.info("No entries yet")
    
    except Exception as e:
        st.error(f"Error loading entries: {e}")

st.divider()

# Digital Twin Visualization
st.subheader("🅿️ Parking Slot Status (Live)")

try:
    twin_path = Path(__file__).parent.parent / "backend" / "mock_digital_twin.json"
    
    if twin_path.exists():
        with open(twin_path) as f:
            twin = json.load(f)
        
        # Group slots by size for better visualization
        slots_by_size = {
            "small": [],
            "medium": [],
            "large": []
        }
        
        for slot in twin["slots"]:
            slots_by_size[slot["size"]].append(slot)
        
        # Display slots grouped by size
        for size, slots in slots_by_size.items():
            if slots:
                st.markdown(f"### {size.upper()} Slots")
                cols = st.columns(min(len(slots), 4))  # Max 4 columns per row
                
                for idx, slot in enumerate(slots):
                    with cols[idx % len(cols)]:
                        status = slot["status"]
                        
                        # Status colors and emojis
                        if status == "free":
                            emoji = "🟢"
                            color = "#28a745"
                            bg_color = "#d4edda"
                            text_color = "#155724"
                        elif status == "reserved":
                            emoji = "🟡"
                            color = "#ffc107"
                            bg_color = "#fff3cd"
                            text_color = "#856404"
                        else:  # occupied
                            emoji = "🔴"
                            color = "#dc3545"
                            bg_color = "#f8d7da"
                            text_color = "#721c24"
                        
                        st.markdown(f"""
                        <div style="
                            padding: 15px; 
                            border-left: 5px solid {color}; 
                            border-radius: 8px; 
                            margin: 5px 0;
                            background-color: {bg_color};
                        ">
                            <h4 style="margin: 0; color: {text_color};">{emoji} Slot {slot['id']}</h4>
                            <p style="margin: 5px 0; color: {text_color};"><b>Size:</b> {slot['size'].upper()}</p>
                            <p style="margin: 5px 0; color: {text_color};"><b>Distance:</b> {slot['distance']}m</p>
                            <p style="margin: 5px 0; color: {text_color};"><b>Status:</b> <strong>{status.upper()}</strong></p>
                        </div>
                        """, unsafe_allow_html=True)
                
                st.write("")  # Spacing between size groups
    
    else:
        st.warning("⚠️ Digital twin file not found. Expected at: backend/mock_digital_twin.json")

except Exception as e:
    st.error(f"❌ Error loading digital twin: {e}")
    import traceback
    st.code(traceback.format_exc())

st.divider()

# Summary Statistics
st.subheader("📊 Summary Statistics")

col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)

try:
    if twin_path.exists():
        with open(twin_path) as f:
            twin = json.load(f)
        
        # Count by size
        small_slots = sum(1 for s in twin["slots"] if s["size"] == "small")
        medium_slots = sum(1 for s in twin["slots"] if s["size"] == "medium")
        large_slots = sum(1 for s in twin["slots"] if s["size"] == "large")
        
        # Count free by size
        small_free = sum(1 for s in twin["slots"] if s["size"] == "small" and s["status"] == "free")
        medium_free = sum(1 for s in twin["slots"] if s["size"] == "medium" and s["status"] == "free")
        large_free = sum(1 for s in twin["slots"] if s["size"] == "large" and s["status"] == "free")
        
        with col_stats1:
            st.metric("Small Slots", f"{small_free}/{small_slots}", delta="Available")
        
        with col_stats2:
            st.metric("Medium Slots", f"{medium_free}/{medium_slots}", delta="Available")
        
        with col_stats3:
            st.metric("Large Slots", f"{large_free}/{large_slots}", delta="Available")
        
        with col_stats4:
            total_entries = occupancy.get("entries", 0)
            st.metric("Active Vehicles", total_entries)

except Exception as e:
    st.error(f"Error loading statistics: {e}")

# Manual refresh button
st.divider()
col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])

with col_btn2:
    if st.button("🔄 Refresh Now", type="primary", use_container_width=True):
        st.session_state.last_refresh_time = time.time()
        st.rerun()

st.caption("🛂 Security Dashboard | Real-time monitoring of parking facility")