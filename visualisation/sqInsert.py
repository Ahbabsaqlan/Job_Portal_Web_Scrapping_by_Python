# import pandas as pd
# import sqlite3

# csv_file = 'Dataset(TSV)/merged_jobs_common_schema.tsv' 
# db_name = 'my_Jobdatabase.db'

# print("Reading CSV...")

# try:
#     # Try 1: Standard read
#     df = pd.read_csv(csv_file)
# except pd.errors.ParserError:
#     print("Standard read failed. Trying auto-detection...")
#     try:
#         # Try 2: Auto-detect separator
#         df = pd.read_csv(csv_file, sep=None, engine='python')
#     except:
#         print("Auto-detection failed. Skipping bad lines...")
#         # Try 3: Force read by skipping bad lines
#         df = pd.read_csv(csv_file, on_bad_lines='skip')

# # Clean column names (remove spaces/dots for SQL)
# df.columns = [c.strip().replace(' ', '_').replace('.', '') for c in df.columns]

# print(f"Read {len(df)} rows. Inserting into SQLite...")

# conn = sqlite3.connect(db_name)
# df.to_sql('job_data', conn, if_exists='replace', index=False)
# conn.close()

# print("Done!")

# import pandas as pd
# import sqlite3

# excel_file = 'jobstreet_id_master_data.xlsx' # Make sure this ends in .xlsx

# # USE read_excel, NOT read_csv
# df = pd.read_excel(excel_file) 

# conn = sqlite3.connect('my_jobstreet_id_database.db')
# df.to_sql('my_table', conn, if_exists='replace', index=False)
# conn.close()
# print("Success")


import pandas as pd

# Load the current merged file
df = pd.read_csv("Dataset(TSV)/merged_jobs_common_schema.tsv", sep='\t', low_memory=False)

# Convert Date
df['Posted On'] = pd.to_datetime(df['Posted On'], errors='coerce')

# FILTER: Keep only July 1st, 2025 onwards
df_filtered = df[df['Posted On'] >= '2025-07-01']

print(f"Original Count: {len(df)}")
print(f"Filtered Count: {len(df_filtered)}")
print(f"Removed {len(df) - len(df_filtered)} outdated/bad records.")

# Save the Clean Version
df_filtered.to_csv("Dataset(TSV)/Final_SSLMD_2025.tsv", sep='\t', index=False)
print("✅ Saved 'Final_SSLMD_2025.tsv'. Use this file for the Supervisor Report.")