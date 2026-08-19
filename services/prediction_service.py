import os
from datetime import datetime

import joblib
import pandas as pd

from services.database_service import get_db_connection


MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "model_artifacts",
    "wait_time_regressor.joblib"
)

MODEL_MAE = 32.68


def _get_latest_snapshot_id(cursor):
    cursor.execute(
        """
        SELECT snapshot_id
        FROM ed_operational_snapshots
        ORDER BY snapshot_id DESC
        LIMIT 1;
        """
    )

    row = cursor.fetchone()

    return row["snapshot_id"] if row else None


def _calculate_representative_esi(high_acuity, low_acuity):
    """
    Convert the operational acuity mix into a representative
    ESI value that can be supplied to the NHAMCS-trained model.

    The Random Forest was trained using patient-level ESI values,
    so this serves as a representative department-level proxy.
    """

    high_acuity = int(high_acuity or 0)
    low_acuity = int(low_acuity or 0)

    total = high_acuity + low_acuity

    if total == 0:
        return 3

    high_ratio = high_acuity / total

    if high_ratio >= 0.60:
        return 2
    elif high_ratio >= 0.30:
        return 3
    else:
        return 4


def _calculate_operational_adjustment(snapshot):
    """
    Apply a transparent operational adjustment to the baseline
    Random Forest prediction.

    The Random Forest was trained on NHAMCS patient-level variables.
    The adjustment layer incorporates the live ED operational
    conditions entered through TriageIQ.
    """

    beds_occupied = float(snapshot["active_beds_occupied"])
    total_beds = max(1.0, float(snapshot["total_beds_configured"]))

    patients_waiting = float(snapshot["patients_waiting"])
    nurses = max(1.0, float(snapshot["available_nurses"]))
    physicians = max(1.0, float(snapshot["available_physicians"]))

    high_acuity = float(snapshot["high_acuity_esi12"])
    low_acuity = float(snapshot["low_acuity_esi45"])

    arrival_rate = float(snapshot["hourly_arrival_rate"])

    occupancy_pct = (beds_occupied / total_beds) * 100.0

    adjustment = 0.0

    # -----------------------------------------------------
    # BED OCCUPANCY PRESSURE
    # -----------------------------------------------------

    if occupancy_pct > 60:
        adjustment += (occupancy_pct - 60) * 0.60

    # -----------------------------------------------------
    # WAITING ROOM PRESSURE
    # -----------------------------------------------------

    adjustment += patients_waiting * 1.20

    # -----------------------------------------------------
    # ARRIVAL RATE PRESSURE
    # -----------------------------------------------------

    adjustment += arrival_rate * 0.80

    # -----------------------------------------------------
    # STAFFING PRESSURE
    # -----------------------------------------------------

    current_patient_load = beds_occupied + patients_waiting

    estimated_staff_capacity = (
        nurses * 4.0
        + physicians * 6.0
    )

    staffing_deficit = max(
        0.0,
        current_patient_load - estimated_staff_capacity
    )

    adjustment += staffing_deficit * 0.80

    # -----------------------------------------------------
    # ACUITY PRESSURE
    # -----------------------------------------------------

    adjustment += high_acuity * 2.50
    adjustment += low_acuity * 0.40

    return adjustment


def generate_wait_time_prediction(snapshot_id=None):
    """
    Generate a wait-time prediction for an ED operational snapshot.

    1. Loads the requested operational snapshot.
    2. Generates a baseline prediction from the trained
       NHAMCS Random Forest model.
    3. Applies a transparent operational adjustment using
       live capacity, staffing, arrival rate, and acuity.
    4. Stores the final prediction in predictive_logs.
    """

    default_result = {
        "predicted_wait_time": 30.0,
        "predicted_wait_minutes": 30.0,
        "mae_lower_bound": 0.0,
        "mae_upper_bound": 62.7
    }

    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # -------------------------------------------------
        # DETERMINE SNAPSHOT
        # -------------------------------------------------

        if snapshot_id is None:
            snapshot_id = _get_latest_snapshot_id(cursor)

        if snapshot_id is None:
            conn.close()
            return default_result

        cursor.execute(
            """
            SELECT *
            FROM ed_operational_snapshots
            WHERE snapshot_id = ?;
            """,
            (snapshot_id,)
        )

        snapshot = cursor.fetchone()

        if not snapshot:
            conn.close()
            return default_result

        # -------------------------------------------------
        # BUILD REPRESENTATIVE ML FEATURES
        # -------------------------------------------------

        representative_esi = _calculate_representative_esi(
            snapshot["high_acuity_esi12"],
            snapshot["low_acuity_esi45"]
        )

        current_hour = datetime.now().hour

        features = pd.DataFrame(
            [
                {
                    "triage_esi": representative_esi,

                    # Representative adult patient used because
                    # operational snapshots do not contain
                    # patient-identifying demographics.
                    "age": 45,

                    # Representative value consistent with
                    # the model training schema.
                    "sex": 1,

                    "arrival_hour": current_hour
                }
            ]
        )

        # -------------------------------------------------
        # RANDOM FOREST BASELINE
        # -------------------------------------------------

        baseline_prediction = 30.0

        if os.path.exists(MODEL_PATH):

            model = joblib.load(MODEL_PATH)

            baseline_prediction = float(
                model.predict(features)[0]
            )

        # -------------------------------------------------
        # OPERATIONAL ADJUSTMENT
        # -------------------------------------------------

        operational_adjustment = (
            _calculate_operational_adjustment(snapshot)
        )

        predicted_val = (
            baseline_prediction
            + operational_adjustment
        )

        # Prevent unrealistic negative values
        predicted_val = max(
            0.0,
            predicted_val
        )

        predicted_val = round(
            predicted_val,
            1
        )

        # -------------------------------------------------
        # MAE ERROR BOUNDS
        # -------------------------------------------------

        lower_bound = max(
            0.0,
            round(
                predicted_val - MODEL_MAE,
                1
            )
        )

        upper_bound = round(
            predicted_val + MODEL_MAE,
            1
        )

        # -------------------------------------------------
        # SAVE / UPDATE PREDICTION LOG
        # -------------------------------------------------

        cursor.execute(
            """
            INSERT INTO predictive_logs (
                snapshot_id,
                predicted_wait_minutes,
                mae_lower_bound,
                mae_upper_bound
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(snapshot_id)
            DO UPDATE SET
                predicted_wait_minutes =
                    excluded.predicted_wait_minutes,

                mae_lower_bound =
                    excluded.mae_lower_bound,

                mae_upper_bound =
                    excluded.mae_upper_bound,

                generation_timestamp =
                    CURRENT_TIMESTAMP;
            """,
            (
                snapshot_id,
                predicted_val,
                lower_bound,
                upper_bound
            )
        )

        conn.commit()
        conn.close()

        return {
            "predicted_wait_time":
                predicted_val,

            "predicted_wait_minutes":
                predicted_val,

            "mae_lower_bound":
                lower_bound,

            "mae_upper_bound":
                upper_bound,

            "baseline_ml_prediction":
                round(
                    baseline_prediction,
                    1
                ),

            "operational_adjustment":
                round(
                    operational_adjustment,
                    1
                )
        }

    except Exception as e:

        if conn:
            try:
                conn.close()
            except Exception:
                pass

        print(
            f"Prediction service error: {e}"
        )

        return default_result