
import streamlit as st, requests, os
from sqlite_helper import init_db, create_booking, get_booking_by_plate, list_bookings
from agentic import dynamic_pricing_agent
init_db()
FLASK_URL = os.environ.get("FLASK_URL","http://localhost:5000")

st.set_page_config(page_title="Parking — Agentic Demo")
st.title("Parking Agentic Demo (Gemini + Langraph ready)")

with st.expander("Current DB & Config"):
    st.write("Flask backend:", FLASK_URL)
    st.write("DB path:", os.environ.get("PARK_DB_PATH","parking.db"))

st.header("Create Booking")
with st.form("book"):
    plate = st.text_input("Plate").upper()
    model = st.text_input("Model")
    size = st.selectbox("Size", ["small","medium","large"])
    if st.form_submit_button("Create"):
        if not plate: st.error("Plate required")
        else:
            create_booking(plate, model, size)
            st.success("Booking saved")

st.header("Approach Gate (simulate)")
plate_a = st.text_input("Approach plate", key="ap")
model_a = st.text_input("Approach model", key="am")
size_a = st.selectbox("Approach size", ["small","medium","large"], key="as")

col1, col2 = st.columns(2)
with col1:
    if st.button("Show dynamic price"):
        st.info(f"Current dynamic price: {dynamic_pricing_agent()}")
with col2:
    if st.button("Approach (call backend)"):
        if not plate_a: st.error("plate required")
        else:
            try:
                r = requests.post(f"{FLASK_URL}/trigger_entry", json={"plate":plate_a,"model":model_a,"size":size_a}, timeout=15)
                if r.status_code==200: st.json(r.json())
                else: st.error(f"backend error {r.status_code}: {r.text}")
            except Exception as e:
                st.error(f"call failed: {e}")

st.markdown("---")
if st.button("Show recent bookings"):
    st.json(list_bookings(30))
