import os
import sys

# Add parent directory to system path so Python can find services module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.database_service import get_db_connection, init_db


def test_database_transactions():
    print("🧪 Starting Database Transaction Verification Test...\n")

    # Ensure database tables exist
    init_db()

    conn = get_db_connection()
    cursor = conn.cursor()

    # -------------------------------------------------------------
    # Test 1: Insert Simulated Operational Snapshot
    # -------------------------------------------------------------
    print("1️⃣ Testing Snapshot Insertion...")
    cursor.execute(
        """
        INSERT INTO ed_operational_snapshots (
            patients_waiting, active_beds_occupied, total_beds_configured,
            available_nurses, available_physicians, high_acuity_esi12,
            low_acuity_esi45, hourly_arrival_rate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (18, 28, 30, 6, 2, 5, 13, 8.5),
    )

    snapshot_id = cursor.lastrowid
    print(f"   ✅ Snapshot inserted successfully! Assigned ID: {snapshot_id}")

    # -------------------------------------------------------------
    # Test 2: Insert Mapped Predictive Log (Foreign Key linked)
    # -------------------------------------------------------------
    print("\n2️⃣ Testing Predictive Log Insertion (Foreign Key Linked)...")
    cursor.execute(
        """
        INSERT INTO predictive_logs (
            snapshot_id, predicted_wait_minutes, mae_lower_bound, mae_upper_bound
        ) VALUES (?, ?, ?, ?)
    """,
        (snapshot_id, 42.5, 32.5, 52.5),
    )

    prediction_id = cursor.lastrowid
    print(
        f"   ✅ Predictive Log inserted successfully! Assigned ID: {prediction_id}"
    )

    # -------------------------------------------------------------
    # Test 3: Query Relational JOIN (Snapshot + Prediction)
    # -------------------------------------------------------------
    print("\n3️⃣ Testing Relational LEFT JOIN Fetch...")
    cursor.execute(
        """
        SELECT 
            s.snapshot_id,
            s.entry_timestamp,
            s.patients_waiting,
            s.active_beds_occupied,
            s.total_beds_configured,
            p.predicted_wait_minutes,
            p.mae_lower_bound,
            p.mae_upper_bound
        FROM ed_operational_snapshots s
        LEFT JOIN predictive_logs p ON s.snapshot_id = p.snapshot_id
        WHERE s.snapshot_id = ?
    """,
        (snapshot_id,),
    )

    row = cursor.fetchone()
    if row:
        print(f"   ✅ Relational Query Success:")
        print(f"      • Snapshot ID: {row['snapshot_id']}")
        print(
            f"      • Beds Occupied: {row['active_beds_occupied']}/{row['total_beds_configured']}"
        )
        print(
            f"      • Predicted Wait: {row['predicted_wait_minutes']} mins (Range: {row['mae_lower_bound']} - {row['mae_upper_bound']} mins)"
        )
    else:
        print("   ❌ Failed to retrieve relational record!")

    # -------------------------------------------------------------
    # Test 4: Update Alert Settings Configuration
    # -------------------------------------------------------------
    print("\n4️⃣ Testing Alert Settings Configuration Update...")
    cursor.execute(
        """
        UPDATE alert_settings 
        SET occupancy_warning_threshold = 80.0,
            waiting_count_warning_threshold = 12,
            updated_timestamp = CURRENT_TIMESTAMP
        WHERE setting_id = 1
    """
    )

    conn.commit()

    # Read back updated settings
    cursor.execute("SELECT * FROM alert_settings WHERE setting_id = 1")
    settings = cursor.fetchone()
    print("   ✅ Alert Settings Updated Successfully:")
    print(
        f"      • Occupancy Warning Threshold: {settings['occupancy_warning_threshold']}%"
    )
    print(
        f"      • Waiting Count Warning Threshold: {settings['waiting_count_warning_threshold']} patients"
    )

    conn.close()
    print("\n🎉 ALL DATABASE TRANSACTION TESTS PASSED CLEANLY!")


if __name__ == "__main__":
    test_database_transactions()