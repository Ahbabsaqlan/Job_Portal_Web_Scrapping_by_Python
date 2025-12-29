import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# ================= CONFIGURATION =================
INPUT_FILE = "Dataset(TSV)/Final_SSLMD_2025.tsv"
REPORT_DIR = "EDA_Report"
os.makedirs(REPORT_DIR, exist_ok=True)

def generate_eda():
    print("--- Loading Dataset ---")
    try:
        # Load data
        df = pd.read_csv(INPUT_FILE, sep='\t', low_memory=False)
        
        # FIX: Force conversion of 'Posted On' to datetime objects
        df['Posted On'] = pd.to_datetime(df['Posted On'], errors='coerce')
        
    except FileNotFoundError:
        print(f"File not found: {INPUT_FILE}")
        return

    print(f"Total Rows: {len(df)}")
    print(f"Total Columns: {len(df.columns)}")
    print("-" * 30)

    # 1. MISSING VALUES
    print("\n[1] MISSING VALUES ANALYSIS")
    missing = df.isnull().sum()
    missing_pct = (df.isnull().sum() / len(df)) * 100
    missing_df = pd.DataFrame({'Missing Count': missing, 'Percentage': missing_pct})
    print(missing_df[missing_df['Missing Count'] > 0].sort_values('Percentage', ascending=False))

    # 2. COUNTRY DISTRIBUTION
    print("\n[2] DISTRIBUTION BY COUNTRY")
    country_counts = df['Country'].value_counts()
    print(country_counts)

    # 3. SALARY INSIGHTS
    print("\n[3] SALARY STATISTICS (USD Annual)")
    # Filter for valid positive salaries
    salary_df = df[df['Salary_USD_Annual'] > 0]
    
    # Remove extreme outliers for the stats print (e.g. > $500k/year in this region is likely parsing noise)
    # This helps get a realistic Mean/Median
    filtered_salary_df = salary_df[salary_df['Salary_USD_Annual'] < 500000]
    
    print(f"Jobs with Disclosed Salary: {len(salary_df)} ({len(salary_df)/len(df)*100:.2f}%)")
    
    # Group by Country
    salary_stats = filtered_salary_df.groupby('Country')['Salary_USD_Annual'].describe()[['count', 'mean', '50%', 'max']]
    salary_stats = salary_stats.rename(columns={'50%': 'median'})
    pd.options.display.float_format = '{:,.2f}'.format
    print(salary_stats)

    # 4. TIME SERIES
    print("\n[4] TEMPORAL COVERAGE")
    # Drop NaT (Not a Time) values for calculation
    valid_dates = df['Posted On'].dropna()
    if not valid_dates.empty:
        min_date = valid_dates.min()
        max_date = valid_dates.max()
        print(f"Earliest Date: {min_date}")
        print(f"Latest Date:   {max_date}")
        print(f"Duration:      {(max_date - min_date).days} days")
    else:
        print("No valid dates found.")

    # ================= PLOTTING =================
    sns.set_theme(style="whitegrid")

    # Plot A: Job Counts
    plt.figure(figsize=(10, 6))
    sns.countplot(y='Country', data=df, order=df['Country'].value_counts().index, palette='viridis', hue='Country', legend=False)
    plt.title('Total Job Postings by Country')
    plt.savefig(os.path.join(REPORT_DIR, '1_country_distribution.png'))
    plt.close()

    # Plot B: Salary Distribution (Box Plot) - Log Scale handles the range differences
    if not filtered_salary_df.empty:
        plt.figure(figsize=(12, 6))
        sns.boxplot(x='Country', y='Salary_USD_Annual', data=filtered_salary_df, palette='Set2', hue='Country', legend=False)
        plt.yscale('log')
        plt.title('Annual Salary Distribution by Country (USD - Log Scale)')
        plt.ylabel('Annual Salary (USD)')
        plt.savefig(os.path.join(REPORT_DIR, '2_salary_distribution.png'))
        plt.close()

    # Plot C: Top Job Titles
    plt.figure(figsize=(10, 8))
    top_titles = df['Job Title'].value_counts().head(15)
    sns.barplot(x=top_titles.values, y=top_titles.index, palette='magma', hue=top_titles.index, legend=False)
    plt.title('Top 15 Most Common Job Titles')
    plt.xlabel('Frequency')
    plt.savefig(os.path.join(REPORT_DIR, '3_top_titles.png'))
    plt.close()

    print(f"\n✅ EDA Complete. Images saved to /{REPORT_DIR}")

if __name__ == "__main__":
    generate_eda()