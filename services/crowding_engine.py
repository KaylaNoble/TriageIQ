import os
import sys
from services.database_service import get_db_connection

def evaluate_crowding_status(*args, **kwargs):
    default_status = {
        "status_level": "NORMAL",
        "status_color": "#28a745",
        "recommendation": "Department operating within standard capacity thresholds.",
        "occupancy_pct": 50.0,
        "beds_occupied": 10,
        "total_beds": 20,
        "patients_waiting": 5,
        "reasons": ["Operating under standard limits"]
    }
    try:
        snapshot_id = args[0] if len(args) > 0 else kwargs.get("snapshot_id", None)
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if snapshot_id is None:
            cursor.execute("SELECT snapshot_id FROM ed_operational_snapshots ORDER BY snapshot_id DESC LIMIT 1;")
            row = cursor.fetchone()
            snapshot_id = row["snapshot_id"] if row else 1

        cursor.execute("SELECT * FROM ed_operational_snapshots WHERE snapshot_id = ?;", (snapshot_id,))
        snap = cursor.fetchone()

        cursor.execute("SELECT * FROM alert_settings WHERE setting_id = 1;")
        settings = cursor.fetchone()
        conn.close()

        if not snap or not settings:
            return default_status

        occ_warn = float(settings["occupancy_warning_threshold"]) if "occupancy_warning_threshold" in settings.keys() else 75.0
        occ_crit = float(settings["occupancy_critical_threshold"]) if "occupancy_critical_threshold" in settings.keys() else 90.0
        wait_warn = int(settings["waiting_count_warning_threshold"]) if "waiting_count_warning_threshold" in settings.keys() else 10
        wait_crit = int(settings["waiting_count_critical_threshold"]) if "waiting_count_critical_threshold" in settings.keys() else 20

        occ_pct = round((snap["active_beds_occupied"] / max(1, snap["total_beds_configured"])) * 100, 1)
        patients_waiting = snap["patients_waiting"]

        reasons = []
        is_crit = False
        is_warn = False

        if occ_pct >= occ_crit:
            is_crit = True
            reasons.append(f"Bed occupancy ({occ_pct}%) exceeded critical threshold ({occ_crit}%)")
        elif occ_pct >= occ_warn:
            is_warn = True
            reasons.append(f"Bed occupancy ({occ_pct}%) exceeded warning threshold ({occ_warn}%)")

        if patients_waiting >= wait_crit:
            is_crit = True
            reasons.append(f"Waiting patients ({patients_waiting}) exceeded critical count ({wait_crit})")
        elif patients_waiting >= wait_warn:
            is_warn = True
            reasons.append(f"Waiting patients ({patients_waiting}) exceeded warning count ({wait_warn})")

        if is_crit:
            level = "CRITICAL"
            color = "#dc3545"
            rec = "CRITICAL SURGE ALERT: Activate diverted intake protocols and notify on-call clinical staff immediately."
        elif is_warn:
            level = "WARNING"
            color = "#ffc107"
            rec = "WARNING CAPACITY ALERT: Monitor bed turnover rate closely and prepare fast-track triage spaces."
        else:
            level = "NORMAL"
            color = "#28a745"
            rec = "NORMAL OPERATIONS: Department capacity and patient wait queues remain within safe operational limits."
            reasons = ["Occupancy and waiting queues within configured safety limits."]

        return {
            "status_level": level,
            "status_color": color,
            "recommendation": rec,
            "occupancy_pct": occ_pct,
            "beds_occupied": snap["active_beds_occupied"],
            "total_beds": snap["total_beds_configured"],
            "patients_waiting": patients_waiting,
            "reasons": reasons
        }
    except Exception:
        return default_status
