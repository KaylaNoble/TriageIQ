import os
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

# Define paths
TRAINING_DATA_PATH = os.path.join("core_data", "nhamcs_processed_training.csv")
MODEL_OUTPUT_DIR = "model_artifacts"
MODEL_OUTPUT_PATH = os.path.join(MODEL_OUTPUT_DIR, "wait_time_regressor.joblib")


def train_and_serialize_model():
    print("⏳ Loading preprocessed training dataset from core_data/nhamcs_processed_training.csv...")

    if not os.path.exists(TRAINING_DATA_PATH):
        print(
            f"❌ Error: Missing preprocessed training dataset at {TRAINING_DATA_PATH}"
        )
        print("Please run python services/preprocess_training_data.py first.")
        return

    df = pd.read_csv(TRAINING_DATA_PATH)
    print(
        f"   ✅ Dataset loaded cleanly: {len(df):,} total clinical visit records."
    )

    # 1. Separate Features (X) and Target (y)
    feature_cols = ["triage_esi", "age", "sex", "arrival_hour"]
    target_col = "wait_time_minutes"

    X = df[feature_cols]
    y = df[target_col]

    # 2. Split into Train (80%) and Test (20%) Sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print(
        f"   📊 Data Split: {len(X_train):,} training samples, {len(X_test):,} validation test samples."
    )
    print("🌲 Training Scikit-Learn Random Forest Regressor model...")

    # 3. Instantiate and Train Random Forest Regressor
    model = RandomForestRegressor(
        n_estimators=100, max_depth=12, random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train)

    # 4. Evaluate Performance on Test Set
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print("\n📈 Model Evaluation Performance (20% Holdout Test Set):")
    print(
        f"   • Mean Absolute Error (MAE): {mae:.2f} minutes (Expected prediction deviation window)"
    )
    print(f"   • R² Coefficient of Determination: {r2:.4f}")

    # 5. Serialize and Save Model Artifact
    os.makedirs(MODEL_OUTPUT_DIR, exist_ok=True)
    joblib.dump(model, MODEL_OUTPUT_PATH)

    print(f"\n🎉 Model Pipeline Successfully Serialized & Saved!")
    print(f"   • Artifact Target Path: {MODEL_OUTPUT_PATH}")


if __name__ == "__main__":
    train_and_serialize_model()