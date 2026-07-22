import os
import sqlite3

# Define absolute or relative path to the SQLite file
DB_PATH = os.path.join("core_data", "triage_store.db")


def get_db_connection():
    """
    Establishes and returns a connection to the SQLite database.
    Enforces row factory for name-based column access and enables foreign keys.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """
    Initializes the SQLite database schema by creating required application tables:
    1. ed_operational_snapshots
    2. predictive_logs
    3. alert_settings

    Includes default baseline configuration seed for alert_settings.
    """
    os.makedirs("core_data", exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Create ed_operational_snapshots table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ed_operational_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            patients_waiting INTEGER NOT NULL,
            active_beds_occupied INTEGER NOT NULL,
            total_beds_configured INTEGER NOT NULL,
            available_nurses INTEGER NOT NULL,
            available_physicians INTEGER NOT NULL,
            high_acuity_esi12 INTEGER NOT NULL,
            low_acuity_esi45 INTEGER NOT NULL,
            hourly_arrival_rate REAL NOT NULL
        );
    """
    )

    # 2. Create predictive_logs table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS predictive_logs (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL UNIQUE,
            generation_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            predicted_wait_minutes REAL NOT NULL,
            mae_lower_bound REAL NOT NULL,
            mae_upper_bound REAL NOT NULL,
            FOREIGN KEY (snapshot_id) REFERENCES ed_operational_snapshots (snapshot_id) ON DELETE CASCADE
        );
    """
    )

    # 3. Create alert_settings table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_settings (
            setting_id INTEGER PRIMARY KEY CHECK (setting_id = 1),
            occupancy_warning_threshold REAL NOT NULL DEFAULT 85.0,
            occupancy_critical_threshold REAL NOT NULL DEFAULT 95.0,
            waiting_count_warning_threshold INTEGER NOT NULL DEFAULT 15,
            waiting_count_critical_threshold INTEGER NOT NULL DEFAULT 30,
            updated_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """
    )

    # Seed default baseline configuration if alert_settings is empty
    cursor.execute("SELECT COUNT(*) FROM alert_settings;")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            """
            INSERT INTO alert_settings (
                setting_id, 
                occupancy_warning_threshold, 
                occupancy_critical_threshold, 
                waiting_count_warning_threshold, 
                waiting_count_critical_threshold
            ) VALUES (1, 85.0, 95.0, 15, 30);
        """
        )

    conn.commit()
    conn.close()
    print("✅ Database schema initialized successfully in core_data/triage_store.db")


if __name__ == "__main__":
    init_db()