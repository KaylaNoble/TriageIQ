import os
import sys
import joblib
import pandas as pd
from datetime import datetime

# Add parent directory to system path so Python finds the services module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.database_service import get_db_connection

MODEL_PATH = os.path.join("model_artifacts", "wait_time_regressor.joblib")
MODEL_MAE = 32.68  # Baseline MAE from Milestone 2.1 evaluation


def load_predictive_model():
    """Loads and returns the serialized Random Forest model pipeline."""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"❌ Model artifact not found at {MODEL_PATH}. Run training script first."
        )
    return joblib.load(MODEL_PATH)


def generate_wait_time_prediction(snapshot_id: int) -> dict:
    """
    Retrieves operational snapshot data by snapshot_id, formats features,
    generates wait time prediction, and logs output to predictive_logs table.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Query the operational snapshot record
    cursor.execute(
        """
        SELECT * FROM ed_operational_snapshots WHERE snapshot_id = ?
    """,
        (snapshot_id,),
    )
    snapshot = cursor.fetchone()

    if not snapshot:
        conn.close()
        raise ValueError(f"❌ Snapshot ID {snapshot_id} not found in database.")

    # 2. Extract and derive feature vector for model input
    high_acuity = snapshot["high_acuity_esi12"]
    low_acuity = snapshot["low_acuity_esi45"]
    
    # Calculate dominant ESI (2 if high acuity heavy, else 3)
    derived_esi = 2 if high_acuity > low_acuity else 3

    # Derive current hour from snapshot entry timestamp or current system time
    entry_time_str = snapshot["entry_timestamp"]
    try:
        arrival_hour = datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S").hour
    except (ValueError, TypeError):
        arrival_hour = datetime.now().hour

    # Default representative demographics for macro operational prediction
    derived_age = 45
    derived_sex = 1

    feature_data = pd.DataFrame(
        [
            {
                "triage_esi": derived_esi,
                "age": derived_age,
                "sex": derived_sex,
                "arrival_hour": arrival_hour,
            }
        ]
    )

    # 3. Load model and run inference
    model = load_predictive_model()
    predicted_wait = float(model.predict(feature_data)[0])

    # Ensure non-negative predicted wait time
    predicted_wait = max(5.0, round(predicted_wait, 1))

    # Calculate MAE bounds
    mae_lower = max(0.0, round(predicted_wait - MODEL_MAE, 1))
    mae_upper = round(predicted_wait + MODEL_MAE, 1)

    # 4. Insert prediction log into database (upsert if existing snapshot entry)
    cursor.execute(
        """
        INSERT INTO predictive_logs (
            snapshot_id, predicted_wait_minutes, mae_lower_bound, mae_upper_bound
        ) VALUES (?, ?, ?, ?)
        ON CONFLICT(snapshot_id) DO UPDATE SET
            predicted_wait_minutes = excluded.predicted_wait_minutes,
            mae_lower_bound = excluded.mae_lower_bound,
            mae_upper_bound = excluded.mae_upper_bound,
            generation_timestamp = CURRENT_TIMESTAMP;
    """,
        (snapshot_id, predicted_wait, mae_lower, mae_upper),
    )

    conn.commit()
    conn.close()

    return {
        "snapshot_id": snapshot_id,
        "predicted_wait_minutes": predicted_wait,
        "mae_lower_bound": mae_lower,
        "mae_upper_bound": mae_upper,
    }


if __name__ == "__main__":
    print("🧪 Running Prediction Inference Service Unit Test...\n")
    # Quick execution against existing test snapshot (ID 1)
    try:
        result = generate_wait_time_prediction(1)
        print("✅ Prediction Inference Service Executed Successfully!")
        print(f"   • Snapshot ID: {result['snapshot_id']}")
        print(f"   • Predicted Wait: {result['predicted_wait_minutes']} mins")
        print(
            f"   • Bounds: [{result['mae_lower_bound']} mins - {result['mae_upper_bound']} mins]"
        )
    except Exception as e:
        print(f"❌ Prediction Service Test Failed: {e}")