# inspect_data.py
import pandas as pd
import os

def run_cdc_inspection():
    # Direct target mapping using your exact filename from the folder
    target_path = "core_data/ed2021-stata.dta"
    
    print("⏳ Locating authentic CDC NHAMCS source registry...")
    if not os.path.exists(target_path):
        print(f"❌ Error: Target dataset missing from 'core_data/' folder.")
        print(f"Looked for '{target_path}'. Please check the filename match.")
        return

    print(f"📖 Ingesting records from: {target_path}")
    
    # Natively parse the Stata file architecture into a Pandas DataFrame
    df = pd.read_stata(target_path, convert_categoricals=False)

    print("\n" + "="*45)
    print("🏥 REAL-TIME CDC NHAMCS DATA PROFILE SUMMARY")
    print("="*45)
    print(f"• Total Logged ED Visits (Rows): {df.shape[0]}")
    print(f"• Total Isolated Variables (Cols): {df.shape[1]}")
    print("-"*45)

    # Core Informatics Variable Auditing (Case-Insensitive Match)
    core_variables = {
        'ARRTIME': 'Patient Arrival Time',
        'LOV': 'Length of Visit (Minutes)',
        'IMMEDR': 'Triage Urgency Category (ESI Proxy)',
        'AGE': 'Patient Age Metric',
        'SEX': 'Patient Biological Sex'
    }

    print("\n🔍 Auditing Feature Candidate Fields:")
    for var, description in core_variables.items():
        matched_col = [col for col in df.columns if col.upper() == var.upper()]
        
        if matched_col:
            actual_name = matched_col[0]
            missing_count = df[actual_name].isna().sum()
            data_type = df[actual_name].dtype
            print(f"✅ Found Column: '{actual_name}' ({description})")
            print(f"   └─ Type: {data_type} | Missing Elements: {missing_count}")
        else:
            print(f"❌ Missing Core Target Variable: '{var}' ({description})")
            
    print("\n📋 Snapshot of Raw Schema Properties:")
    print(df.head(3))
    print("="*45)

if __name__ == "__main__":
    run_cdc_inspection()