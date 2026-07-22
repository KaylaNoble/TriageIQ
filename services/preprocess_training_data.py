import os
import pandas as pd

# Define paths
RAW_DATA_PATH = os.path.join("core_data", "ed2021-stata.dta")
PROCESSED_DATA_PATH = os.path.join("core_data", "nhamcs_processed_training.csv")


def preprocess_nhamcs_dataset():
    print("⏳ Loading raw CDC NHAMCS dataset from core_data/ed2021-stata.dta...")

    if not os.path.exists(RAW_DATA_PATH):
        print(f"❌ Error: Could not find raw data file at {RAW_DATA_PATH}")
        return

    # 1. Read Stata file with convert_categoricals=False to avoid duplicate value label errors
    df = pd.read_stata(RAW_DATA_PATH, convert_categoricals=False)
    print(f"   ✅ Raw dataset loaded successfully: {len(df):,} total visit records.")

    # Convert column names to uppercase for consistent mapping
    df.columns = [col.upper() for col in df.columns]

    # 2. Identify required variables
    # WAITTIME: Wait time in minutes to see a physician/provider
    # IMMEDR: Triage immediacy/acuity level (1=Immediate, 2=Emergent, 3=Urgent, 4=Semi-urgent, 5=Non-urgent)
    # AGE: Patient age in years
    # SEX: Biological sex (1=Female, 2=Male in CDC raw codes)
    # ARRTIME: Arrival time string/numeric
    target_col = "WAITTIME"
    feature_cols = ["IMMEDR", "AGE", "SEX"]

    # Verify column existence
    missing_cols = [
        col for col in [target_col] + feature_cols if col not in df.columns
    ]
    if missing_cols:
        print(f"❌ Error: Missing expected CDC variables: {missing_cols}")
        return

    print("🧹 Cleaning missing values and filtering valid clinical records...")

    # 3. Filter valid WAITTIME records (CDC uses negative numbers/9999 for missing/not applicable)
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")
    valid_df = df[
        (df[target_col] >= 0) & (df[target_col] < 1440)
    ].copy()  # Filter valid wait times (0 to 24 hours)

    # 4. Clean Triage Acuity (IMMEDR)
    # CDC IMMEDR valid range is 1 to 5
    valid_df["IMMEDR"] = pd.to_numeric(valid_df["IMMEDR"], errors="coerce")
    valid_df = valid_df[valid_df["IMMEDR"].isin([1, 2, 3, 4, 5])].copy()

    # 5. Extract arrival hour if ARRTIME is available
    if "ARRTIME" in valid_df.columns:
        valid_df["ARRIVAL_HOUR"] = (
            pd.to_numeric(valid_df["ARRTIME"], errors="coerce")
            .fillna(12)
            .astype(int)
            % 24
        )
    else:
        valid_df["ARRIVAL_HOUR"] = 12

    # Clean SEX column
    valid_df["SEX"] = pd.to_numeric(valid_df["SEX"], errors="coerce").fillna(1).astype(int)

    # Select target columns for training dataset
    clean_dataset = pd.DataFrame(
        {
            "wait_time_minutes": valid_df[target_col],
            "triage_esi": valid_df["IMMEDR"].astype(int),
            "age": valid_df["AGE"].astype(int),
            "sex": valid_df["SEX"].astype(int),
            "arrival_hour": valid_df["ARRIVAL_HOUR"].astype(int),
        }
    )

    # Save to CSV
    clean_dataset.to_csv(PROCESSED_DATA_PATH, index=False)

    print(f"\n🎉 Standalone Training Dataset Successfully Preprocessed!")
    print(f"   • Output File: {PROCESSED_DATA_PATH}")
    print(f"   • Filtered Clean Rows: {len(clean_dataset):,} records")
    print(
        f"   • Target Variable: wait_time_minutes (Mean: {clean_dataset['wait_time_minutes'].mean():.1f} mins)"
    )
    print("\nSample Processed Head:")
    print(clean_dataset.head())


if __name__ == "__main__":
    preprocess_nhamcs_dataset()