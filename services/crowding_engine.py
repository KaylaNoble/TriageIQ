import os
import sys

# Add parent directory to system path so Python finds the services module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.database_service import get_db_connection


def evaluate_crowding_status(snapshot_id: int) -> dict:
    """
    Evaluates operational crowding status for a given snapshot ID against
    manager-configurable thresholds stored in the alert_settings table.
    
    Returns a dictionary with alert level, metric details, and action recommendations.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fetch Operational Snapshot Data
    cursor.execute(
        "SELECT * FROM ed_operational_snapshots WHERE snapshot_id = ?;",
        (snapshot_id,),
    )
    snapshot = cursor.fetchone()

    if not snapshot:
        conn.close()
        raise ValueError(f"❌ Snapshot ID {snapshot_id} not found in database.")

    # 2. Fetch Manager Alert Threshold Settings
    cursor.execute("SELECT * FROM alert_settings WHERE setting_id = 1;")
    settings = cursor.fetchone()

    conn.close()

    if not settings:
        # Fallback defaults if table is unseeded
        occ_warn, occ_crit = 85.0, 95.0
        wait_warn, wait_crit = 15, 30
    else:
        occ_warn = settings["occupancy_warning_threshold"]
        occ_crit = settings["occupancy_critical_threshold"]
        wait_warn = settings["waiting_count_warning_threshold"]
        wait_crit = settings["waiting_count_critical_threshold"]

    # 3. Calculate Core Capacity Metrics
    beds_occupied = snapshot["active_beds_occupied"]
    beds_total = snapshot["total_beds_configured"]
    patients_waiting = snapshot["patients_waiting"]

    occupancy_pct = (
        round((beds_occupied / beds_total) * 100, 1) if beds_total > 0 else 0.0
    )

    # 4. Multi-Tiered Rule Evaluation
    reasons = []
    status_level = "NORMAL"
    status_color = "#28a745"  # Green

    # Check Critical Criteria
    if occupancy_pct >= occ_crit:
        reasons.append(f"Bed occupancy ({occupancy_pct}%) reached CRITICAL threshold (≥{occ_crit}%).")
        status_level = "CRITICAL"
    if patients_waiting >= wait_crit:
        reasons.append(f"Waiting patient count ({patients_waiting}) reached CRITICAL threshold (≥{wait_crit}).")
        status_level = "CRITICAL"

    # Check Warning Criteria (if not already Critical)
    if status_level != "CRITICAL":
        if occupancy_pct >= occ_warn:
            reasons.append(f"Bed occupancy ({occupancy_pct}%) reached WARNING threshold (≥{occ_warn}%).")
            status_level = "WARNING"
        if patients_waiting >= wait_warn:
            reasons.append(f"Waiting patient count ({patients_waiting}) reached WARNING threshold (≥{wait_warn}).")
            status_level = "WARNING"

    # Set Color Code and Recommendations based on final level
    if status_level == "CRITICAL":
        status_color = "#dc3545"  # Red
        recommendation = "CRITICAL CROWDING: Initiate surge protocol, notify shift supervisor, and divert non-emergent walk-ins if permitted."
    elif status_level == "WARNING":
        status_color = "#ffc107"  # Yellow/Gold
        recommendation = "ELEVATED CROWDING: Expedite discharge processing, review pending bed turnover, and prepare overflow area."
    else:
        reasons.append("All operational capacity metrics are within safe baseline parameters.")
        recommendation = "NORMAL OPERATIONS: Standard triage workflow and bed assignment active."

    return {
        "snapshot_id": snapshot_id,
        "status_level": status_level,
        "status_color": status_color,
        "occupancy_pct": occupancy_pct,
        "patients_waiting": patients_waiting,
        "beds_occupied": beds_occupied,
        "total_beds": beds_total,
        "reasons": reasons,
        "recommendation": recommendation,
    }


if __name__ == "__main__":
    print("🧪 Running Rule-Based Crowding Engine Unit Test...\n")
    try:
        # Test against Snapshot ID 1 (28/30 beds = 93.3% occupancy, 18 waiting patients)
        eval_result = evaluate_crowding_status(1)
        print("✅ Crowding Engine Evaluated Successfully!")
        print(f"   • Snapshot ID: {eval_result['snapshot_id']}")
        print(f"   • Status Level: {eval_result['status_level']}")
        print(f"   • Occupancy: {eval_result['occupancy_pct']}% ({eval_result['beds_occupied']}/{eval_result['total_beds']} beds)")
        print(f"   • Patients Waiting: {eval_result['patients_waiting']}")
        print("   • Triggered Reasons:")
        for r in eval_result["reasons"]:
            print(f"      - {r}")
        print(f"   • Recommendation: {eval_result['recommendation']}")
    except Exception as e:
        print(f"❌ Crowding Engine Test Failed: {e}")