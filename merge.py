import os
import pandas as pd
import re
import numpy as np
from dateutil import parser as date_parser

# ======================= CONFIGURATION =======================
BASE_DIR = "" 
OUTPUT_DIR = "Dataset(TSV)"
os.makedirs(OUTPUT_DIR, exist_ok=True)

FILE_METADATA = {
    "bdjobs_master_data.xlsx": { "source": "BDJobs", "country": "Bangladesh" },
    "naukri_master_data.xlsx": { "source": "Naukri", "country": "India" },
    "rozee_master_data.xlsx": { "source": "Rozee", "country": "Pakistan" },
    "jobstreet_id_master_data.xlsx": { "source": "JobStreet", "country": "Indonesia" },
    "jobstreet_ph_master_data.xlsx": { "source": "JobStreet", "country": "Philippines" },
    "jobstreet_sg_master_data.xlsx": { "source": "JobStreet", "country": "Singapore" }
}

EXCHANGE_RATES = {
    'India': 0.012, 'Bangladesh': 0.0085, 'Pakistan': 0.0036,
    'Singapore': 0.74, 'Indonesia': 0.000064, 'Philippines': 0.018
}

FINAL_COLUMNS = [
    'Job ID', 'Job Title', 'Company Name', 'Location', 'Posted On',
    'Experience', 'Education Requirements', 'Skills Required',
    'Job Description', 'Salary Range', 'Additional Requirements',
    'Job Link', 'Source', 'Country'
]

DUPLICATE_CHECK_COLUMNS = ['Job Title', 'Company Name', 'Posted On', 'Location']
OUTPUT_MERGED_FILE = "merged_jobs_common_schema.tsv"

# ======================= ROBUST DATE PARSING =======================

def clean_and_parse_date(date_val):
    """
    Handles formats: 
    - 2025-12-16 10:25:56 (Naukri New)
    - 2025-07-25 (Naukri Old)
    - Dec 23, 2025 (BDJobs)
    - Excel Serial Dates or NaTs
    """
    if pd.isna(date_val) or str(date_val).strip() == "":
        return pd.NaT
    
    date_str = str(date_val).strip()
    
    try:
        # Pandas is usually smart enough if we force non-strict mode
        # We try to convert strictly first, if fail, we let dateutil handle it
        return pd.to_datetime(date_str)
    except:
        try:
            # Fallback: dateutil is very good at "Dec 23, 2025"
            return pd.to_datetime(date_parser.parse(date_str))
        except:
            return pd.NaT

# ======================= SALARY PARSING LOGIC =======================

def parse_local_amount(salary_str):
    if pd.isna(salary_str) or str(salary_str).strip() == "":
        return np.nan
    
    # Lowercase and convert to string
    text = str(salary_str).lower().strip()
    
    # Quick exit for non-salary text
    if any(x in text for x in ["not disclosed", "negotiable", "confidential", "competitive"]):
        return np.nan

    # Clean commas (e.g., "50,000" -> "50000")
    text_clean = text.replace(',', '')

    # 1. Determine Multiplier
    multiplier = 1.0
    if 'crore' in text_clean or 'cr' in text_clean:
        multiplier = 10000000.0
    elif 'lacs' in text_clean or 'lakh' in text_clean or 'lpa' in text_clean:
        multiplier = 100000.0
    elif 'k ' in text_clean or text_clean.endswith('k'):
        multiplier = 1000.0

    # 2. Extract Numbers (Handling decimals like 2.5)
    numbers = re.findall(r'(\d+(?:\.\d+)?)', text_clean)
    
    if not numbers:
        return np.nan

    # Convert to floats
    try:
        clean_nums = [float(n) for n in numbers]
    except ValueError:
        return np.nan

    # Logic Check: If a number is interpreted as a year (e.g., "2-5 years"), 
    # it usually appears small (<= 30).
    # However, "2.5 Lakh" is also small. Multiplier saves us here.
    # If no multiplier is found and value is < 50, it's likely not a monthly/yearly salary 
    # (unless it's hourly, which we ignore for this scale).
    
    avg_val = sum(clean_nums) / len(clean_nums)
    
    # Filter out junk small numbers if no multiplier exists (e.g. "Year 2025")
    if multiplier == 1.0 and avg_val < 100:
        return np.nan
        
    final_val = avg_val * multiplier
    return final_val

def get_salary_in_usd(salary_str, country, source):
    # Only process if valid string
    if pd.isna(salary_str): return np.nan

    raw_amount = parse_local_amount(salary_str)
    
    if pd.isna(raw_amount) or raw_amount == 0:
        return np.nan
        
    exchange_rate = EXCHANGE_RATES.get(country, 0)
    usd_amount = raw_amount * exchange_rate
    
    # Naukri/India = Yearly. Others = Monthly -> Annualize
    if source == 'Naukri' or country == 'India':
        final_annual_usd = usd_amount
    else:
        final_annual_usd = usd_amount * 12

    return round(final_annual_usd, 2)

# ======================= MAIN PROCESS =======================

def convert_and_merge():
    print("--- Step 1: Loading & Converting ---")
    
    dfs = []
    
    for filename, metadata in FILE_METADATA.items():
        filepath = os.path.join(BASE_DIR, filename)
        if not os.path.exists(filepath):
            continue
            
        print(f"Processing {filename}...")
        try:
            df = pd.read_excel(filepath, engine='openpyxl')
            
            # Create Standard DF
            std_df = pd.DataFrame()
            
            # Copy available columns
            for col in FINAL_COLUMNS:
                if col in df.columns:
                    std_df[col] = df[col]
                else:
                    std_df[col] = np.nan # Create missing columns

            # 1. Smart Column Filling
            if 'Location' not in df.columns and 'City' in df.columns:
                std_df['Location'] = df['City']
            if 'Job Description' not in df.columns and 'Job Description Snippet' in df.columns:
                std_df['Job Description'] = df['Job Description Snippet']
            if 'Experience' not in df.columns and 'Experience Required' in df.columns:
                std_df['Experience'] = df['Experience Required']
                
            # 2. Salary Range Merging (Min/Max -> Range)
            if 'Salary Range' not in df.columns:
                if 'Min Salary' in df.columns and 'Max Salary' in df.columns:
                    std_df['Salary Range'] = df['Min Salary'].astype(str) + " - " + df['Max Salary'].astype(str)

            std_df['Source'] = metadata['source']
            std_df['Country'] = metadata['country']
            
            dfs.append(std_df[FINAL_COLUMNS]) # Ensure strict column order
            
        except Exception as e:
            print(f"Error reading {filename}: {e}")

    print("\n--- Step 2: Merging ---")
    merged_df = pd.concat(dfs, ignore_index=True)
    print(f"Total Rows Raw: {len(merged_df)}")
    
    # Deduplication
    merged_df.drop_duplicates(subset=DUPLICATE_CHECK_COLUMNS, keep='first', inplace=True)
    print(f"Rows After Dedup: {len(merged_df)}")

    print("\n--- Step 3: Preprocessing & Enrichment ---")

    # 1. ROBUST DATE PARSING
    print("  -> Parsing Dates (Handling Mixed Formats)...")
    # Convert to string first to avoid mixed-type failures
    merged_df['Posted On'] = merged_df['Posted On'].astype(str).apply(clean_and_parse_date)

    # 2. Region
    south_asia = ['Bangladesh', 'India', 'Pakistan']
    merged_df['Region'] = merged_df['Country'].apply(lambda x: 'South Asia' if x in south_asia else 'South East Asia')

    # 3. CLEAN TEXT
    text_cols = ['Job Title', 'Company Name', 'Location', 'Skills Required']
    for col in text_cols:
        merged_df[col] = merged_df[col].astype(str).str.strip().replace(['nan', 'NaT', 'None'], 'Not Specified')

    # 4. SALARY CALCULATION
    print("  -> Calculating Salaries...")
    merged_df['Salary_USD_Annual'] = merged_df.apply(
        lambda row: get_salary_in_usd(row['Salary Range'], row['Country'], row['Source']), 
        axis=1
    )
    
    # --- DEBUG SALARY ---
    # Print 5 examples of valid salaries found to ensure it works
    valid_salaries = merged_df[merged_df['Salary_USD_Annual'] > 0].head(5)
    if not valid_salaries.empty:
        print("\n✅ DEBUG: Sample Successful Conversions:")
        print(valid_salaries[['Salary Range', 'Country', 'Salary_USD_Annual']])
    else:
        print("\n⚠️ WARNING: No valid salaries calculated. Check Parsing Logic.")
        # Debug: Print raw salary range examples
        print("Raw Salary Samples:", merged_df['Salary Range'].dropna().head(5).tolist())
    # --------------------

    output_path = os.path.join(OUTPUT_DIR, OUTPUT_MERGED_FILE)
    merged_df.to_csv(output_path, sep='\t', index=False)
    print(f"\nSaved to {output_path}")

if __name__ == "__main__":
    convert_and_merge()

# import os
# import pandas as pd

# # ======================= CONFIGURATION =======================
# # --- The directory where your Excel files are located ---
# # (Leave as "" if the script is in the same folder as the files)
# BASE_DIR = "" 

# # --- List of your input Excel files ---
# INPUT_FILES = [
#     "bdjobs_master_data.xlsx",
#     "naukri_master_data.xlsx",
#     "rozee_master_data.xlsx",
#     "jobstreet_id_master_data.xlsx",
#     "jobstreet_ph_master_data.xlsx",
#     "jobstreet_sg_master_data.xlsx"
# ]

# # --- The name of the output summary Excel file ---
# OUTPUT_SUMMARY_FILE = "data_summary_report.xlsx"
# # =============================================================


# def visualize_data_summary_to_excel():
#     """
#     Reads multiple Excel files, generates a summary of row counts,
#     column counts, and value counts for each column, and saves
#     this summary to a new, clean Excel file.
#     """
#     summary_data_list = []

#     print("--- Generating Data Summary Report ---\n")

#     # 1. Loop through each file to gather its statistics
#     for filename in INPUT_FILES:
#         file_path = os.path.join(BASE_DIR, filename)
        
#         try:
#             print(f"Analyzing file: {filename}...")
#             df = pd.read_excel(file_path, engine='openpyxl')

#             # Create a dictionary to hold this file's summary
#             file_summary = {
#                 'File Name': filename,
#                 'Total Rows': df.shape[0],
#                 'Total Columns': df.shape[1]
#             }

#             # Get the count of non-empty values for each column
#             column_value_counts = df.count().to_dict()
#             file_summary.update(column_value_counts)

#             summary_data_list.append(file_summary)
#             print(f"  -> Analysis complete.")

#         except FileNotFoundError:
#             print(f"  -> ‼️ WARNING: File not found: {file_path}. Skipping.")
#         except Exception as e:
#             print(f"  -> ‼️ ERROR: Could not read {file_path}. Reason: {e}. Skipping.")

#     if not summary_data_list:
#         print("\nNo data files were analyzed. Exiting.")
#         return

#     # 2. Create a single summary DataFrame
#     summary_df = pd.DataFrame(summary_data_list)
#     summary_df.set_index('File Name', inplace=True)

#     # 3. Clean up the table
#     summary_df.fillna(0, inplace=True)
#     summary_df = summary_df.astype(int)

#     # 4. Reorder columns for a logical view
#     all_column_names = sorted([col for col in summary_df.columns if col not in ['Total Rows', 'Total Columns']])
#     final_column_order = ['Total Rows', 'Total Columns'] + all_column_names
#     summary_df = summary_df[final_column_order]
    
#     # 5. Save the summary DataFrame to an Excel file
#     output_path = os.path.join(BASE_DIR, OUTPUT_SUMMARY_FILE)
#     try:
#         summary_df.to_excel(output_path, engine='openpyxl')
        
#         print("\n" + "="*50)
#         print(" " * 15 + "SUMMARY REPORT GENERATED")
#         print("="*50)
#         print(f"\nA structured summary has been saved to the Excel file:")
#         print(f"  -> {output_path}")
#         print("\nPlease open this file to view the detailed summary.")
#         print("="*50)

#     except Exception as e:
#         print(f"\n‼️ ERROR: Could not save the summary Excel file. Reason: {e}")


# if __name__ == "__main__":
#     visualize_data_summary_to_excel()