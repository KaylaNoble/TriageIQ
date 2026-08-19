import streamlit as st
import pandas as pd
import sqlite3

def render_dashboard():
    st.title("🏥 Live Operations Dashboard")
    st.markdown("Real-time clinical flow, bed capacity, and predictive wait-time analytics.")

    # 1. Fetch latest snapshot from SQLite
    try:
        conn = sqlite3.connect("core_data/triage_store.db")
        cursor = conn.cursor()
        
        # Load Alert Thresholds
        cursor.execute("SELECT warning_occupancy, critical_occupancy, warning_wait_count, critical_wait_count FROM alert_settings WHERE id = 1")
        settings = cursor.fetchone()
        if settings:
            warn_occ, crit_occ, warn_wait, crit_wait = settings
        else:
            warn_occ, crit_occ, warn_wait, crit_wait = (80.0, 95.0, 12, 20)

        # Load Latest Operational Snapshot
        cursor.execute("""
            SELECT occupied_beds, total_beds, patients_waiting, on_duty_nurses, on_duty_physicians, 
                   hourly_arrival_rate, high_acuity_count, low_acuity_count, timestamp
            FROM ed_operational_snapshots 
            ORDER BY id DESC LIMIT 1
        """)
        snapshot = cursor.fetchone()
        conn.close()
    except Exception:
        snapshot = None
        warn_occ, crit_occ, warn_wait, crit_wait = (80.0, 95.0, 12, 20)

    # Baseline defaults if database is empty
    if snapshot:
        occ_beds, total_beds, patients_waiting, nurses, physicians, arrival_rate, high_acuity, low_acuity, last_updated = snapshot
    else:
        occ_beds, total_beds, patients_waiting, nurses, physicians, arrival_rate, high_acuity, low_acuity = (20, 50, 4, 10, 4, 3, 1, 3)
        last_updated = "Simulated / Default"

    occupancy_pct = (occ_beds / total_beds) * 100.0 if total_beds > 0 else 0.0

    # 2. Status Banner Alert Assessment
    if occupancy_pct >= crit_occ or patients_waiting >= crit_wait:
        st.error(f"🚨 **CRITICAL SURGE ALERT**: Bed Occupancy ({occupancy_pct:.1f}%) or Waiting Queue ({patients_waiting}) exceeds critical thresholds!")
    elif occupancy_pct >= warn_occ or patients_waiting >= warn_wait:
        st.warning(f"⚠️ **CAPACITY WARNING**: Operational metrics approaching surge warning limits.")
    else:
        st.success(f"✅ **NORMAL OPERATIONS**: Department capacity is stable. Bed Occupancy: {occupancy_pct:.1f}% | Waiting: {patients_waiting}")

    st.markdown("---")
    # 4. Live Queue Table
    st.subheader("📋 Active Waiting Room Queue")

    if patients_waiting > 0:
        base_wait = 15.0  # Base wait estimate in minutes

        # Build markdown table header
        table_md = "| Queue Position | Acuity Level | Estimated Wait Time | Status |\n"
        table_md += "| :--- | :--- | :--- | :--- |\n"

        # Starts at #1 and creates exactly the number of
        # patients currently reported as waiting.
        for pos in range(1, int(patients_waiting) + 1):
            is_high = pos <= high_acuity

            acuity = (
                "ESI 2 - Emergent"
                if is_high
                else "ESI 4 - Semi-Urgent"
            )

            wait = f"{int(pos * base_wait)} mins"

            status = (
                "Priority Triage"
                if is_high
                else "Waiting for Bed"
            )

            table_md += (
                f"| #{pos} | {acuity} | "
                f"{wait} | {status} |\n"
            )

        st.markdown(table_md)

    else:
        st.info("The waiting room is currently empty.")