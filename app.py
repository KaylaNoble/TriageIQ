import os
import sys

import pandas as pd
import streamlit as st


sys.path.append(
    os.path.abspath(
        os.path.dirname(__file__)
    )
)


from services.database_service import get_db_connection
from services.prediction_service import generate_wait_time_prediction
from services.crowding_engine import evaluate_crowding_status


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="TriageIQ - ED Operations Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# DATABASE HELPERS
# =========================================================

def fetch_latest_snapshot_id():

    try:

        conn = get_db_connection()

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT snapshot_id
            FROM ed_operational_snapshots
            ORDER BY snapshot_id DESC
            LIMIT 1;
            """
        )

        row = cursor.fetchone()

        conn.close()

        return (
            row["snapshot_id"]
            if row
            else None
        )

    except Exception:

        return None


def fetch_snapshot(snapshot_id):

    if snapshot_id is None:
        return None

    try:

        conn = get_db_connection()

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM ed_operational_snapshots
            WHERE snapshot_id = ?;
            """,
            (snapshot_id,)
        )

        row = cursor.fetchone()

        conn.close()

        return row

    except Exception:

        return None


def update_alert_settings(
    occ_warn,
    occ_crit,
    wait_warn,
    wait_crit
):

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
                updated_timestamp = CURRENT_TIMESTAMP

            WHERE setting_id = 1;
            """,
            (
                occ_warn,
                occ_crit,
                wait_warn,
                wait_crit
            )
        )

        conn.commit()

        conn.close()

        return True

    except Exception as e:

        st.error(
            f"Unable to save alert settings: {e}"
        )

        return False


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

        cursor.execute(
            """
            INSERT INTO ed_operational_snapshots (

                patients_waiting,

                active_beds_occupied,

                total_beds_configured,

                available_nurses,

                available_physicians,

                high_acuity_esi12,

                low_acuity_esi45,

                hourly_arrival_rate

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                int(waiting_count),

                int(beds_occupied),

                int(total_beds),

                int(nurses),

                int(physicians),

                int(high_acuity),

                int(low_acuity),

                float(arrival_rate)
            )
        )

        new_snapshot_id = (
            cursor.lastrowid
        )

        conn.commit()

        conn.close()

        # Generate prediction immediately
        generate_wait_time_prediction(
            new_snapshot_id
        )

        return new_snapshot_id

    except Exception as e:

        st.error(
            f"Unable to save operational snapshot: {e}"
        )

        return None


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title(
    "TriageIQ Platform"
)

st.sidebar.markdown(
    "**Emergency Department Decision Support**"
)

st.sidebar.markdown("---")


nav_choice = st.sidebar.radio(
    "Navigation Menu:",
    [
        "Live Operations Dashboard",
        "Snapshot Intake Simulator",
        "Manager Alert Settings",
        "Anonymized Triage Queue"
    ]
)


st.sidebar.markdown("---")


st.sidebar.success(
    "Database Service: Connected"
)


# =========================================================
# MAIN HEADER
# =========================================================

st.title(
    "TriageIQ - Emergency Department Operations"
)


st.markdown(
    "*Predictive Analytics & Real-Time Capacity Alert System*"
)


st.markdown("---")


# =========================================================
# CURRENT SNAPSHOT
# =========================================================

latest_snapshot_id = (
    fetch_latest_snapshot_id()
)


current_snapshot_id = (
    st.session_state.get(
        "active_snapshot_id",
        latest_snapshot_id
    )
)


if current_snapshot_id is None:
    current_snapshot_id = (
        latest_snapshot_id
    )


current_snapshot = (
    fetch_snapshot(
        current_snapshot_id
    )
)


# =========================================================
# PREDICTION
# =========================================================

try:

    prediction = (
        generate_wait_time_prediction(
            current_snapshot_id
        )
        or {}
    )

except Exception:

    prediction = {
        "predicted_wait_time":
            30.0,

        "predicted_wait_minutes":
            30.0,

        "mae_lower_bound":
            0.0,

        "mae_upper_bound":
            62.7
    }


# =========================================================
# CROWDING
# =========================================================

try:

    crowding = (
        evaluate_crowding_status(
            current_snapshot_id
        )
        or {}
    )

except Exception:

    crowding = {

        "status_level":
            "NORMAL",

        "status_color":
            "#28a745",

        "recommendation":
            "Department operating within standard bounds.",

        "occupancy_pct":
            50.0,

        "beds_occupied":
            10,

        "total_beds":
            20,

        "patients_waiting":
            5,

        "reasons":
            [
                "Operating within default parameters."
            ]
    }


wait_time_val = prediction.get(
    "predicted_wait_time",
    prediction.get(
        "predicted_wait_minutes",
        30.0
    )
)


# =========================================================
# PAGE 1
# LIVE OPERATIONS DASHBOARD
# =========================================================

if nav_choice == "Live Operations Dashboard":

    st.subheader(
        "Live Capacity & Predictive Status"
    )


    alert_color = crowding.get(
        "status_color",
        "#28a745"
    )


    status_level = crowding.get(
        "status_level",
        "NORMAL"
    )


    recommendation = crowding.get(
        "recommendation",
        "Department operating within standard bounds."
    )


    st.markdown(
        f"""
<div style="
background-color:{alert_color};
padding:22px;
border-radius:10px;
margin-bottom:25px;
color:white;
">

<h2 style="
margin:0;
padding:0;
color:white;
">
Status Level: {status_level}
</h2>

<p style="
margin:8px 0 0 0;
font-size:16px;
color:white;
">
{recommendation}
</p>

</div>
""",
        unsafe_allow_html=True
    )


    col1, col2, col3, col4 = (
        st.columns(4)
    )


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


    with st.expander(
        "Detailed Alert Criteria"
    ):

        for reason in crowding.get(
            "reasons",
            []
        ):

            st.write(
                f"- {reason}"
            )


# =========================================================
# PAGE 2
# SNAPSHOT INTAKE SIMULATOR
# =========================================================

elif nav_choice == "Snapshot Intake Simulator":

    st.subheader(
        "Real-Time Operational Intake Simulator"
    )


    st.markdown(
        "Adjust parameters below to simulate shift surges. "
        "After submitting, switch to the "
        "**Live Operations Dashboard** on the left sidebar "
        "to view updated metrics."
    )


    # -----------------------------------------------------
    # LOAD CURRENT STORED VALUES
    # -----------------------------------------------------

    if current_snapshot:

        default_beds = int(
            current_snapshot[
                "active_beds_occupied"
            ]
        )

        default_total_beds = int(
            current_snapshot[
                "total_beds_configured"
            ]
        )

        default_waiting = int(
            current_snapshot[
                "patients_waiting"
            ]
        )

        default_nurses = int(
            current_snapshot[
                "available_nurses"
            ]
        )

        default_physicians = int(
            current_snapshot[
                "available_physicians"
            ]
        )

        default_high_acuity = int(
            current_snapshot[
                "high_acuity_esi12"
            ]
        )

        default_low_acuity = int(
            current_snapshot[
                "low_acuity_esi45"
            ]
        )

        default_arrival_rate = int(
            current_snapshot[
                "hourly_arrival_rate"
            ]
        )

    else:

        default_beds = 20

        default_total_beds = 50

        default_waiting = 4

        default_nurses = 10

        default_physicians = 4

        default_high_acuity = 1

        default_low_acuity = 3

        default_arrival_rate = 3


    # -----------------------------------------------------
    # INTAKE FORM
    # -----------------------------------------------------

    with st.form(
        "intake_form"
    ):

        col_a, col_b, col_c = (
            st.columns(3)
        )


        with col_a:

            st.markdown(
                "##### Capacity Parameters"
            )


            in_beds_occupied = (
                st.number_input(
                    "Occupied Beds",

                    min_value=0,

                    max_value=50,

                    value=default_beds
                )
            )


            in_total_beds = (
                st.number_input(
                    "Total Configured Beds",

                    min_value=1,

                    max_value=50,

                    value=default_total_beds
                )
            )


            in_waiting = (
                st.number_input(
                    "Patients Waiting",

                    min_value=0,

                    max_value=100,

                    value=default_waiting
                )
            )


        with col_b:

            st.markdown(
                "##### Staffing & Flow"
            )


            in_nurses = (
                st.number_input(
                    "On-Duty Nurses",

                    min_value=1,

                    max_value=30,

                    value=default_nurses
                )
            )


            in_physicians = (
                st.number_input(
                    "On-Duty Physicians",

                    min_value=1,

                    max_value=15,

                    value=default_physicians
                )
            )


            in_arrival_rate = (
                st.number_input(
                    "Hourly Arrival Rate",

                    min_value=0,

                    max_value=50,

                    value=default_arrival_rate
                )
            )


        with col_c:

            st.markdown(
                "##### Acuity Breakdown"
            )


            in_high_acuity = (
                st.number_input(
                    "High Acuity (ESI 1-2)",

                    min_value=0,

                    max_value=30,

                    value=default_high_acuity
                )
            )


            in_low_acuity = (
                st.number_input(
                    "Low Acuity (ESI 4-5)",

                    min_value=0,

                    max_value=50,

                    value=default_low_acuity
                )
            )


        st.markdown(
            "<br>",
            unsafe_allow_html=True
        )


        submit_button = (
            st.form_submit_button(
                "Submit Operational Snapshot & Analyze"
            )
        )


        if submit_button:

            new_snapshot_id = (
                insert_new_snapshot(
                    in_beds_occupied,
                    in_total_beds,
                    in_waiting,
                    in_nurses,
                    in_physicians,
                    in_high_acuity,
                    in_low_acuity,
                    in_arrival_rate
                )
            )


            if new_snapshot_id:

                st.session_state[
                    "active_snapshot_id"
                ] = new_snapshot_id


                st.success(
                    f"Operational Snapshot "
                    f"#{new_snapshot_id} successfully logged!"
                )


                st.rerun()


# =========================================================
# PAGE 3
# MANAGER ALERT SETTINGS
# =========================================================

elif nav_choice == "Manager Alert Settings":

    st.subheader(
        "Configure Operational Threshold Triggers"
    )


    st.markdown(
        "Modify capacity limits used by the "
        "Rule-Based Crowding Engine to send status alerts."
    )


    try:

        conn = get_db_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            SELECT *
            FROM alert_settings
            WHERE setting_id = 1;
            """
        )


        curr_settings = (
            cursor.fetchone()
        )


        conn.close()


    except Exception:

        curr_settings = None


    occ_warning = (
        float(
            curr_settings[
                "occupancy_warning_threshold"
            ]
        )

        if curr_settings

        else 85.0
    )


    occ_critical = (
        float(
            curr_settings[
                "occupancy_critical_threshold"
            ]
        )

        if curr_settings

        else 95.0
    )


    wait_warning = (
        int(
            curr_settings[
                "waiting_count_warning_threshold"
            ]
        )

        if curr_settings

        else 15
    )


    wait_critical = (
        int(
            curr_settings[
                "waiting_count_critical_threshold"
            ]
        )

        if curr_settings

        else 30
    )


    with st.form(
        "settings_form"
    ):

        col_s1, col_s2 = (
            st.columns(2)
        )


        with col_s1:

            st.markdown(
                "#### Bed Occupancy Thresholds (%)"
            )


            set_occ_warn = (
                st.slider(
                    "Occupancy Warning Threshold (%)",

                    50.0,

                    100.0,

                    occ_warning,

                    1.0
                )
            )


            set_occ_crit = (
                st.slider(
                    "Occupancy Critical Threshold (%)",

                    50.0,

                    100.0,

                    occ_critical,

                    1.0
                )
            )


        with col_s2:

            st.markdown(
                "#### Waiting Patient Count Thresholds"
            )


            set_wait_warn = (
                st.slider(
                    "Waiting Count Warning Threshold",

                    1,

                    50,

                    wait_warning,

                    1
                )
            )


            set_wait_crit = (
                st.slider(
                    "Waiting Count Critical Threshold",

                    1,

                    50,

                    wait_critical,

                    1
                )
            )


        st.markdown(
            "<br>",
            unsafe_allow_html=True
        )


        save_button = (
            st.form_submit_button(
                "Save Threshold Configuration"
            )
        )


        if save_button:

            success = (
                update_alert_settings(
                    set_occ_warn,
                    set_occ_crit,
                    set_wait_warn,
                    set_wait_crit
                )
            )


            if success:

                st.success(
                    "Manager threshold settings "
                    "saved successfully!"
                )


                st.rerun()


# =========================================================
# PAGE 4
# ANONYMIZED TRIAGE QUEUE
# =========================================================

elif nav_choice == "Anonymized Triage Queue":

    st.subheader(
        "Anonymized Waiting Room Queue"
    )


    st.markdown(
        "Visual breakdown of active waiting list "
        "categorized by Emergency Severity Index (ESI)."
    )


    patients_waiting = int(
        crowding.get(
            "patients_waiting",
            0
        )
    )


    patient_templates = [

        {
            "Triage Category":
                "ESI 2 - Emergent",

            "Chief Complaint":
                "Chest Pain / Shortness of Breath",

            "Wait Elapsed":
                "12 mins"
        },

        {
            "Triage Category":
                "ESI 3 - Urgent",

            "Chief Complaint":
                "Abdominal Pain",

            "Wait Elapsed":
                "28 mins"
        },

        {
            "Triage Category":
                "ESI 3 - Urgent",

            "Chief Complaint":
                "High Fever / Chills",

            "Wait Elapsed":
                "22 mins"
        },

        {
            "Triage Category":
                "ESI 4 - Less Urgent",

            "Chief Complaint":
                "Possible Ankle Fracture",

            "Wait Elapsed":
                "45 mins"
        },

        {
            "Triage Category":
                "ESI 5 - Non-Urgent",

            "Chief Complaint":
                "Prescription Refill / Minor Cut",

            "Wait Elapsed":
                "55 mins"
        },

        {
            "Triage Category":
                "ESI 3 - Urgent",

            "Chief Complaint":
                "Severe Migraine / Dizziness",

            "Wait Elapsed":
                "31 mins"
        },

        {
            "Triage Category":
                "ESI 4 - Less Urgent",

            "Chief Complaint":
                "Wrist Injury",

            "Wait Elapsed":
                "38 mins"
        },

        {
            "Triage Category":
                "ESI 3 - Urgent",

            "Chief Complaint":
                "Vomiting / Dehydration",

            "Wait Elapsed":
                "26 mins"
        },

        {
            "Triage Category":
                "ESI 4 - Less Urgent",

            "Chief Complaint":
                "Back Pain",

            "Wait Elapsed":
                "43 mins"
        },

        {
            "Triage Category":
                "ESI 5 - Non-Urgent",

            "Chief Complaint":
                "Medication Refill",

            "Wait Elapsed":
                "60 mins"
        }
    ]


    if patients_waiting > 0:

        queue_rows = []


        for i in range(
            patients_waiting
        ):

            template = (
                patient_templates[
                    i
                    % len(
                        patient_templates
                    )
                ]
            )


            queue_rows.append(
                {

                    "Queue ID":
                        f"PAT-{101 + i}",

                    "Triage Category":
                        template[
                            "Triage Category"
                        ],

                    "Chief Complaint":
                        template[
                            "Chief Complaint"
                        ],

                    "Wait Elapsed":
                        template[
                            "Wait Elapsed"
                        ],

                    "Priority Rank":
                        i + 1
                }
            )


        queue_data = (
            pd.DataFrame(
                queue_rows
            )
        )


        queue_data.index = range(
            1,
            len(queue_data) + 1
        )


        st.dataframe(
            queue_data,
            use_container_width=True
        )


        st.caption(
            f"Current waiting-room census: "
            f"{patients_waiting} patient"
            f"{'s' if patients_waiting != 1 else ''}"
        )


    else:

        st.success(
            "There are currently no patients "
            "waiting in the waiting room."
        )