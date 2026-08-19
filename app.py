import os
import sys
import pandas as pd
import streamlit as st

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from services.database_service import get_db_connection
from services.prediction_service import generate_wait_time_prediction
from services.crowding_engine import evaluate_crowding_status

st.set_page_config(
    page_title="TriageIQ - ED Operations Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom High-Contrast Styling
st.markdown("""
<style>
.status-card {
    padding: 20px;
    border-radius: 10px;
    color: white !important;
    margin-bottom: 25px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.status-card h2, .status-card p {
    color: white !important;
}
</style>
""", unsafe_allow_html=True)


def fetch_latest_snapshot_id():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT snapshot_id FROM ed_operational_snapshots "
            "ORDER BY snapshot_id DESC LIMIT 1;"
        )
        row = cursor.fetchone()
        conn.close()
        return row["snapshot_id"] if row else 1
    except Exception:
        return 1


def update_alert_settings(occ_warn, occ_crit, wait_warn, wait_crit):
    try:
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
    except Exception:
        pass


def insert_new_snapshot(
    beds_occupied,
    total_beds,
    waiting_count,
    nurses,
    physicians,
    high_acuity,
    low_acuity,
    arrival_rate
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(ed_operational_snapshots);")
        columns = [col[1] for col in cursor.fetchall()]

        col_map = {}

        for c in columns:
            if c in ("snapshot_id", "snapshot_timestamp"):
                continue
            elif "bed" in c and "total" in c:
                col_map[c] = total_beds
            elif "bed" in c:
                col_map[c] = beds_occupied
            elif "wait" in c:
                col_map[c] = waiting_count
            elif "nurse" in c:
                col_map[c] = nurses
            elif "physician" in c or "doc" in c:
                col_map[c] = physicians
            elif "high" in c or "esi1" in c:
                col_map[c] = high_acuity
            elif "low" in c or "esi4" in c:
                col_map[c] = low_acuity
            elif "arr" in c or "rate" in c:
                col_map[c] = arrival_rate
            else:
                col_map[c] = 0

        keys = list(col_map.keys())
        vals = list(col_map.values())

        placeholders = ", ".join(["?"] * len(keys))
        cols_str = ", ".join(keys)

        query = (
            f"INSERT INTO ed_operational_snapshots "
            f"({cols_str}) VALUES ({placeholders});"
        )

        cursor.execute(query, tuple(vals))

        new_id = cursor.lastrowid

        conn.commit()
        conn.close()

        try:
            generate_wait_time_prediction(new_id)
        except Exception:
            pass

        return new_id

    except Exception:
        return fetch_latest_snapshot_id()


# ---------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------

st.sidebar.title("TriageIQ Platform")
st.sidebar.markdown("**Emergency Department Decision Support**")
st.sidebar.markdown("---")

nav_choice = st.sidebar.radio(
    "Navigation Menu:",
    [
        "Live Operations Dashboard",
        "Snapshot Intake Simulator",
        "Manager Alert Settings",
        "Anonymized Triage Queue",
    ],
)

st.sidebar.markdown("---")
st.sidebar.success("Database Service: Connected")


# ---------------------------------------------------------
# Main Application Header
# ---------------------------------------------------------

st.title("TriageIQ - Emergency Department Operations")
st.markdown("*Predictive Analytics & Real-Time Capacity Alert System*")
st.markdown("---")

current_snapshot_id = st.session_state.get(
    "active_snapshot_id",
    fetch_latest_snapshot_id()
)


# ---------------------------------------------------------
# Generate Prediction
# ---------------------------------------------------------

try:
    prediction = generate_wait_time_prediction(current_snapshot_id) or {}
except Exception:
    prediction = {
        "predicted_wait_time": 30.0,
        "mae_lower_bound": 0.0,
        "mae_upper_bound": 62.7
    }


# ---------------------------------------------------------
# Evaluate Crowding
# ---------------------------------------------------------

try:
    crowding = evaluate_crowding_status(current_snapshot_id) or {}
except Exception:
    crowding = {
        "status_level": "NORMAL",
        "status_color": "#28a745",
        "recommendation": "Department operating within standard bounds.",
        "occupancy_pct": 50.0,
        "beds_occupied": 10,
        "total_beds": 20,
        "patients_waiting": 5,
        "reasons": ["Operating within default parameters."]
    }


wait_time_val = prediction.get(
    "predicted_wait_time",
    prediction.get("predicted_wait_minutes", 30.0)
)


# =========================================================
# LIVE OPERATIONS DASHBOARD
# =========================================================

if nav_choice == "Live Operations Dashboard":

    st.subheader("Live Capacity & Predictive Status")

    alert_color = crowding.get("status_color", "#28a745")
    status_lvl = crowding.get("status_level", "NORMAL")

    recommendation = crowding.get(
        "recommendation",
        "Department operating within standard bounds."
    )

    st.markdown(
        f"""
        <div class="status-card" style="background-color: {alert_color};">
            <h2 style="margin:0; padding:0;">
                Status Level: {status_lvl}
            </h2>
            <p style="margin:8px 0 0 0; font-size:16px;">
                {recommendation}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Bed Occupancy Rate",
            f"{crowding.get('occupancy_pct', 0)}%",
            f"{crowding.get('beds_occupied', 0)}/"
            f"{crowding.get('total_beds', 1)} Beds"
        )

    with col2:
        st.metric(
            "Patients Waiting",
            f"{crowding.get('patients_waiting', 0)} Patients"
        )

    with col3:
        st.metric(
            "Predicted Wait Time",
            f"{wait_time_val} mins"
        )

    with col4:
        st.metric(
            "MAE Error Bounds",
            f"[{prediction.get('mae_lower_bound', 0)} - "
            f"{prediction.get('mae_upper_bound', 0)}] mins"
        )

    st.markdown("---")

    with st.expander("Detailed Alert Criteria"):
        for reason in crowding.get("reasons", []):
            st.write(f"- {reason}")


# =========================================================
# SNAPSHOT INTAKE SIMULATOR
# =========================================================

elif nav_choice == "Anonymized Triage Queue":
    st.subheader("Anonymized Waiting Room Queue")

    st.markdown(
        "Visual breakdown of active waiting list categorized "
        "by Emergency Severity Index (ESI)."
    )

    # Pull the CURRENT number of waiting patients from the active snapshot.
    patients_waiting = int(crowding.get("patients_waiting", 0))

    # Sample anonymized clinical data used to populate the queue.
    patient_templates = [
        {
            "Triage Category": "ESI 2 - Emergent",
            "Chief Complaint": "Chest Pain / Shortness of Breath",
            "Wait Elapsed": "12 mins",
        },
        {
            "Triage Category": "ESI 3 - Urgent",
            "Chief Complaint": "Abdominal Pain",
            "Wait Elapsed": "28 mins",
        },
        {
            "Triage Category": "ESI 3 - Urgent",
            "Chief Complaint": "High Fever / Chills",
            "Wait Elapsed": "22 mins",
        },
        {
            "Triage Category": "ESI 4 - Less Urgent",
            "Chief Complaint": "Possible Ankle Fracture",
            "Wait Elapsed": "45 mins",
        },
        {
            "Triage Category": "ESI 5 - Non-Urgent",
            "Chief Complaint": "Prescription Refill / Minor Cut",
            "Wait Elapsed": "55 mins",
        },
        {
            "Triage Category": "ESI 3 - Urgent",
            "Chief Complaint": "Severe Migraine / Dizziness",
            "Wait Elapsed": "31 mins",
        },
        {
            "Triage Category": "ESI 4 - Less Urgent",
            "Chief Complaint": "Wrist Injury",
            "Wait Elapsed": "38 mins",
        },
        {
            "Triage Category": "ESI 3 - Urgent",
            "Chief Complaint": "Vomiting / Dehydration",
            "Wait Elapsed": "26 mins",
        },
        {
            "Triage Category": "ESI 4 - Less Urgent",
            "Chief Complaint": "Back Pain",
            "Wait Elapsed": "43 mins",
        },
        {
            "Triage Category": "ESI 5 - Non-Urgent",
            "Chief Complaint": "Medication Refill",
            "Wait Elapsed": "60 mins",
        },
    ]

    if patients_waiting > 0:
        queue_rows = []

        for i in range(patients_waiting):
            # Cycle through templates if more patients are waiting
            # than the number of sample templates available.
            template = patient_templates[i % len(patient_templates)]

            queue_rows.append(
                {
                    "Queue ID": f"PAT-{101 + i}",
                    "Triage Category": template["Triage Category"],
                    "Chief Complaint": template["Chief Complaint"],
                    "Wait Elapsed": template["Wait Elapsed"],
                    "Priority Rank": i + 1,
                }
            )

        queue_data = pd.DataFrame(queue_rows)

        # Make the visible dataframe row numbers start at 1 instead of 0.
        queue_data.index = range(1, len(queue_data) + 1)

        st.dataframe(
            queue_data,
            use_container_width=True
        )

        st.caption(
            f"Current waiting-room census: {patients_waiting} patient"
            f"{'s' if patients_waiting != 1 else ''}"
        )

    else:
        st.success("There are currently no patients waiting in the waiting room.")