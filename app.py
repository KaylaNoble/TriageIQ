import streamlit as st

st.set_page_config(page_title='TriageIQ MVP Shell', layout='wide')

st.title('?? TriageIQ Platform - MVP Interface Shell')
st.markdown('---')

st.sidebar.title('Navigation Control')
view_selection = st.sidebar.radio('Select Interface Layer', ['Home Overview', 'Data Ingestion', 'Analytics Dashboard'])

if view_selection == 'Home Overview':
    st.success('? Main Application Shell Container Loaded.')
    st.info('Clinical operational parameters pipeline: Awaiting CDC data mapping.')
else:
    st.warning('Module Under Development: View logic will be mapped in the upcoming sprints.')

import os
import sys
import pandas as pd
import streamlit as st

# Ensure parent directory is in path for module imports
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from services.database_service import get_db_connection
from services.prediction_service import generate_wait_time_prediction
from services.crowding_engine import evaluate_crowding_status

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="TriageIQ — ED Wait-Time & Crowding Dashboard",
    page_icon="🏥",
    layout="wide",
)

st.title("🏥 TriageIQ — Emergency Department Operations Dashboard")
st.markdown(
    "**Predictive Analytics & Real-Time Capacity Alert System for Charge Nurses**"
)
st.markdown("---")


# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------
def fetch_latest_snapshot_id():
    """Fetches the most recent operational snapshot ID from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT snapshot_id FROM ed_operational_snapshots ORDER BY snapshot_id DESC LIMIT 1;")
    row = cursor.fetchone()
    conn.close()
    return row["snapshot_id"] if row else 1


def update_alert_settings(occ_warn, occ_crit, wait_warn, wait_crit):
    """Updates manager threshold parameters in alert_settings table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE alert_settings
        SET occupancy_warning_threshold = ?,
            occupancy_critical_threshold = ?,
            waiting_count_warning_threshold = ?,
            waiting_count_critical_threshold = ?,
            last_updated_timestamp = CURRENT_TIMESTAMP
        WHERE setting_id = 1;
    """,
        (occ_warn, occ_crit, wait_warn, wait_crit),
    )
    conn.commit()
    conn.close()


def insert_new_snapshot(beds_occupied, total_beds, waiting_count, nurses, physicians, high_acuity, low_acuity, arrival_rate):
    """Inserts a new operational snapshot into database and runs prediction & crowding evaluation."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO ed_operational_snapshots (
            active_beds_occupied, total_beds_configured, patients_waiting,
            on_duty_nurses, on_duty_physicians, high_acuity_esi12,
            low_acuity_esi45, hourly_arrival_rate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """,
        (beds_occupied, total_beds, waiting_count, nurses, physicians, high_acuity, low_acuity, arrival_rate),
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Trigger inference service and crowding engine for new snapshot
    generate_wait_time_prediction(new_id)
    return new_id


# -------------------------------------------------------------------
# Main Layout: Tabs
# -------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "📊 Real-Time Operations & Predictions",
    "⚙️ Manager Alert Threshold Settings",
    "📋 Anonymized Triage Queue",
])


# ===================================================================
# TAB 1: Real-Time Dashboard & Simulation Intake
# ===================================================================
with tab1:
    st.subheader("📍 Live Department Status")

    # Fetch latest operational state
    current_snapshot_id = st.session_state.get("active_snapshot_id", fetch_latest_snapshot_id())
    
    # Run prediction & crowding evaluations
    prediction = generate_wait_time_prediction(current_snapshot_id)
    crowding = evaluate_crowding_status(current_snapshot_id)

    # 1. Alert Banner
    alert_color = crowding["status_color"]
    st.markdown(
        f"""
        <div style="background-color: {alert_color}; padding: 15px; border-radius: 8px; color: white; margin-bottom: 20px;">
            <h3 style="margin:0; padding:0; color: white;">Status Level: {crowding['status_level']}</h3>
            <p style="margin:5px 0 0 0; font-size: 16px;">{crowding['recommendation']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. Key Metrics Display
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Bed Occupancy Rate", f"{crowding['occupancy_pct']}%", f"{crowding['beds_occupied']}/{crowding['total_beds']} Beds")
    with col2:
        st.metric("Patients Waiting", f"{crowding['patients_waiting']} Patients")
    with col3:
        st.metric("Predicted Wait Time", f"{prediction['predicted_wait_minutes']} mins")
    with col4:
        st.metric("MAE Error Bounds", f"[{prediction['mae_lower_bound']} - {prediction['mae_upper_bound']}] mins")

    # Display triggered reasons
    with st.expander("🔍 View Triggered Alert Criteria"):
        for reason in crowding["reasons"]:
            st.write(f"• {reason}")

    st.markdown("---")

    # 3. Simulation & Snapshot Data Entry Intake Form
    st.subheader("📝 Real-Time Snapshot Intake Simulator")
    st.markdown("Adjust shift parameters below to simulate changing ED workload and re-evaluate predictive metrics.")

    with st.form("intake_form"):
        col_a, col_b, col_c = st.columns(3)

        with col_a:
            in_beds_occupied = st.number_input("Occupied Beds", min_value=0, max_value=50, value=crowding["beds_occupied"])
            in_total_beds = st.number_input("Total Configured Beds", min_value=1, max_value=50, value=crowding["total_beds"])
            in_waiting = st.number_input("Patients Waiting", min_value=0, max_value=100, value=crowding["patients_waiting"])

        with col_b:
            in_nurses = st.number_input("On-Duty Nurses", min_value=1, max_value=30, value=8)
            in_physicians = st.number_input("On-Duty Physicians", min_value=1, max_value=15, value=3)
            in_arrival_rate = st.number_input("Hourly Arrival Rate", min_value=0, max_value=50, value=12)

        with col_c:
            in_high_acuity = st.number_input("High Acuity Patients (ESI 1-2)", min_value=0, max_value=30, value=4)
            in_low_acuity = st.number_input("Low Acuity Patients (ESI 4-5)", min_value=0, max_value=50, value=10)

        submit_btn = st.form_submit_button("🚀 Submit Operational Snapshot & Analyze")

        if submit_btn:
            new_snap_id = insert_new_snapshot(
                in_beds_occupied, in_total_beds, in_waiting,
                in_nurses, in_physicians, in_high_acuity, in_low_acuity, in_arrival_rate
            )
            st.session_state["active_snapshot_id"] = new_snap_id
            st.success(f"✅ Operational Snapshot #{new_snap_id} successfully logged to database!")
            st.rerun()


# ===================================================================
# TAB 2: Manager Alert Threshold Settings
# ===================================================================
with tab2:
    st.subheader("⚙️ Configure Capacity Warning & Critical Thresholds")
    st.markdown("Adjust the operational triggers used by the Rule-Based Crowding Engine to send status alerts.")

    # Fetch current settings from database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alert_settings WHERE setting_id = 1;")
    curr_settings = cursor.fetchone()
    conn.close()

    with st.form("settings_form"):
        col_s1, col_s2 = st.columns(2)

        with col_s1:
            st.markdown("#### 🛏️ Bed Occupancy Thresholds (%)")
            set_occ_warn = st.slider("Occupancy Warning Threshold (%)", 50.0, 100.0, float(curr_settings["occupancy_warning_threshold"]), 1.0)
            set_occ_crit = st.slider("Occupancy Critical Threshold (%)", 50.0, 100.0, float(curr_settings["occupancy_critical_threshold"]), 1.0)

        with col_s2:
            st.markdown("#### ⏳ Waiting Patient Count Thresholds")
            set_wait_warn = st.slider("Waiting Count Warning Threshold", 1, 50, int(curr_settings["waiting_count_warning_threshold"]), 1)
            set_wait_crit = st.slider("Waiting Count Critical Threshold", 1, 50, int(curr_settings["waiting_count_critical_threshold"]), 1)

        save_settings_btn = st.form_submit_button("💾 Save Threshold Configuration")

        if save_settings_btn:
            update_alert_settings(set_occ_warn, set_occ_crit, set_wait_warn, set_wait_crit)
            st.success("✅ Manager threshold settings saved successfully to database!")
            st.rerun()


# ===================================================================
# TAB 3: Anonymized Triage Queue View
# ===================================================================
with tab3:
    st.subheader("📋 Simulated Anonymized Waiting Room Queue")
    st.markdown("Visual breakdown of current waiting room queue categorized by Emergency Severity Index (ESI).")

    # Representative sample triage queue dataframe
    queue_data = pd.DataFrame([
        {"Queue ID": "PAT-101", "Triage Category": "ESI 2 - Emergent", "Chief Complaint": "Chest Pain / Shortness of Breath", "Wait Elapsed": "12 mins", "Priority Rank": 1},
        {"Queue ID": "PAT-102", "Triage Category": "ESI 3 - Urgent", "Chief Complaint": "Abdominal Pain", "Wait Elapsed": "28 mins", "Priority Rank": 2},
        {"Queue ID": "PAT-103", "Triage Category": "ESI 3 - Urgent", "Chief Complaint": "High Fever / Chills", "Wait Elapsed": "22 mins", "Priority Rank": 3},
        {"Queue ID": "PAT-104", "Triage Category": "ESI 4 - Less Urgent", "Chief Complaint": "Possible Ankle Fracture", "Wait Elapsed": "45 mins", "Priority Rank": 4},
        {"Queue ID": "PAT-105", "Triage Category": "ESI 5 - Non-Urgent", "Chief Complaint": "Prescription Refill / Minor Cut", "Wait Elapsed": "55 mins", "Priority Rank": 5},
    ])

    st.dataframe(queue_data, use_container_width=True)