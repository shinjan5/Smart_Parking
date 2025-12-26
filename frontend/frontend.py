import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import time
from datetime import datetime
import pytz

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from backend.sqlite_helper import (
    create_booking, 
    get_booking_by_plate, 
    get_recent_entries,
    get_recent_detections,
    get_entry_by_plate
)

st.set_page_config(page_title="Smart Parking - Customer Portal", page_icon="🚗", layout="wide")

# Title
st.title("🚗 Smart Parking - Customer Portal")

# Auto-refresh for status updates
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh Entry Status", value=False)
if auto_refresh:
    refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 3, 30, 5)
    time.sleep(refresh_interval)
    st.session_state.last_refresh = time.time()
    st.rerun()

st.sidebar.caption(f"Last updated: {time.strftime('%H:%M:%S', time.localtime(st.session_state.last_refresh))}")


def format_timestamp(iso_timestamp):
    """Convert ISO timestamp to readable format"""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        
        tz = pytz.timezone('Asia/Kolkata')  
        dt_local = dt.replace(tzinfo=pytz.UTC).astimezone(tz)
        return dt_local.strftime("%Y-%m-%d %I:%M:%S %p")
    except:
        return iso_timestamp


# Main layout
tab1, tab2, tab3 = st.tabs(["📋 Pre-Booking", "🔍 Check Status", "📊 Entry Dashboard"])

# ==================== TAB 1: PRE-BOOKING ====================
with tab1:
    st.header("📋 Pre-Book Your Parking Spot")
    
    st.info("""
    **How it works:**
    1. Enter your vehicle details below
    2. Drive to the gate when ready
    3. Our cameras will automatically detect your license plate
    4. AI will assign you the optimal parking slot
    5. Park in your assigned spot - no manual check-in needed!
    """)
    
    with st.form("booking_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            plate = st.text_input(
                "License Plate Number *", 
                max_chars=20,
                placeholder="e.g., ABC1234",
                help="Enter your license plate number (alphanumeric only)"
            ).upper()
            
            model = st.text_input(
                "Car Model *", 
                placeholder="e.g., Honda Civic",
                help="Enter your vehicle model"
            )
        
        with col2:
            size = st.selectbox(
                "Vehicle Size *", 
                ["small", "medium", "large"],
                help="Select your vehicle size for optimal slot allocation"
            )
            
            st.write("")  # Spacing
            st.write("")  # Spacing
        
        submit = st.form_submit_button("🎫 Create Pre-Booking", type="primary", use_container_width=True)
        
        if submit:
            if not plate or not model:
                st.error("❌ Please fill in all required fields")
            elif len(plate) < 4:
                st.error("❌ License plate must be at least 4 characters")
            else:
                try:
                    # Check if booking already exists
                    existing = get_booking_by_plate(plate)
                    if existing:
                        st.warning(f"⚠️ Booking already exists for plate {plate}")
                        st.json(existing)
                    else:
                        create_booking(plate, model, size)
                        st.success(f"✅ Pre-booking created successfully!")
                        st.balloons()
                        
                        st.info(f"""
                        **Next Steps:**
                        - Your plate: **{plate}**
                        - Vehicle: **{model}** ({size})
                        - Status: **Awaiting entry**
                        
                        Drive to the gate and our system will handle the rest!
                        """)
                        
                        time.sleep(1)
                        st.rerun()
                
                except Exception as e:
                    st.error(f"❌ Error creating booking: {e}")

#TAB 2: CHECK STATUS
with tab2:
    st.header("🔍 Check Booking & Entry Status")
    
    col_search, col_result = st.columns([1, 2])
    
    with col_search:
        lookup_plate = st.text_input(
            "Enter License Plate", 
            key="lookup",
            placeholder="ABC1234"
        ).upper()
        
        search_btn = st.button("🔎 Search", type="primary", use_container_width=True)
    
    with col_result:
        if search_btn and lookup_plate:
            try:
                # Check booking first
                booking = get_booking_by_plate(lookup_plate)
                
                if booking:
                    st.success(f"✅ Booking found for **{lookup_plate}**")
                    
                    # Display booking details
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
                    
                    # Check if vehicle has entered using the helper
                    entry = get_entry_by_plate(lookup_plate)
                    
                    if entry:
                        st.success("🎉 **Vehicle has entered parking!**")
                        st.write(f"- **Slot:** {entry['slot_id']}")
                        st.write(f"- **Price:** ${entry['price']}")
                        st.write(f"- **Entry Time:** {format_timestamp(entry['entered_at'])}")
                        
                        # Show visual confirmation
                        st.markdown(f"""
                        <div style="background-color: #d4edda; padding: 20px; border-radius: 10px; border-left: 5px solid #28a745;">
                            <h3 style="color: #155724; margin: 0;">✅ Entry Confirmed</h3>
                            <p style="color: #155724; margin-top: 10px;">
                                Your vehicle <strong>{lookup_plate}</strong> is parked in <strong>Slot {entry['slot_id']}</strong>
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("⏳ Vehicle not yet entered. Proceed to gate for entry.")
                        
                        # Check if there have been any detections
                        from backend.sqlite_helper import get_conn
                        conn = get_conn()
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT COUNT(*) FROM detections WHERE plate=?",
                            (lookup_plate,)
                        )
                        detection_count = cur.fetchone()[0]
                        conn.close()
                        
                        if detection_count > 0:
                            st.warning(f"📸 Your plate has been detected {detection_count} time(s) but entry is still processing...")
                            st.info("💡 **Tip:** Try refreshing this page in a few seconds or enable auto-refresh in the sidebar.")
                
                else:
                    st.warning(f"⚠️ No booking found for **{lookup_plate}**")
                    st.info("Please create a pre-booking first in the Pre-Booking tab.")
            
            except Exception as e:
                st.error(f"❌ Error: {e}")
                import traceback
                st.code(traceback.format_exc())
        
        elif search_btn:
            st.warning("Please enter a license plate number")

# ==================== TAB 3: ENTRY DASHBOARD ====================
with tab3:
    st.header("📊 Recent Entry Activity")
    
    col_refresh = st.columns([4, 1])
    with col_refresh[1]:
        if st.button("🔄 Refresh", use_container_width=True):
            st.session_state.last_refresh = time.time()
            st.rerun()
    
    # Recent Entries
    st.subheader("✅ Recent Entries")
    try:
        entries = get_recent_entries(limit=15)
        
        if entries:
            # Format timestamps before creating dataframe
            formatted_entries = []
            for plate, slot_id, price, entered_at in entries:
                formatted_entries.append([
                    plate, 
                    slot_id, 
                    price, 
                    format_timestamp(entered_at)
                ])
            
            df = pd.DataFrame(formatted_entries, columns=["Plate", "Slot ID", "Price ($)", "Entered At"])
            
            # Highlight most recent
            if len(df) > 0:
                st.success(f"Latest: **{df.iloc[0]['Plate']}** → Slot **{df.iloc[0]['Slot ID']}** | ${df.iloc[0]['Price ($)']}")
            
            st.dataframe(df, use_container_width=True, height=300)
        else:
            st.info("No entries yet. Vehicles will appear here after entering through the gate.")
    
    except Exception as e:
        st.error(f"Error loading entries: {e}")
    
    st.divider()
    
    # Recent Detections
    st.subheader("🎥 Recent Plate Detections")
    try:
        detections = get_recent_detections(limit=10)
        
        if detections:
            # Format detection timestamps
            formatted_detections = []
            for plate, detected_at in detections:
                formatted_detections.append([
                    plate,
                    format_timestamp(detected_at)
                ])
            
            df_det = pd.DataFrame(formatted_detections, columns=["Plate", "Detected At"])
            st.dataframe(df_det, use_container_width=True, height=200)
        else:
            st.info("No detections yet.")
    
    except Exception as e:
        st.error(f"Error loading detections: {e}")

# Footer
st.divider()
st.caption("🚗 Smart Parking System | Pre-booking required for entry | Camera-based automatic recognition")