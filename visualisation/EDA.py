import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# ================= CONFIGURATION =================
INPUT_FILE = "Dataset(TSV)/Final_SSLMD_2025.tsv" # Ensure this is the filtered file
OUTPUT_DIR = "Interactive_Report"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_visuals():
    print("--- Loading Data for Visualization ---")
    try:
        df = pd.read_csv(INPUT_FILE, sep='\t', low_memory=False)
    except FileNotFoundError:
        print("Please run the filtering script to generate Final_SSLMD_2025.tsv first.")
        return

    # Cleanup for visual safety
    df['Country'] = df['Country'].astype(str)
    df['Job Title'] = df['Job Title'].astype(str).str.title()
    
    # Color Palette (Professional)
    colors = px.colors.qualitative.Bold

    # ================= 1. THE BIG PICTURE: MAP =================
    print("Generating Map...")
    country_counts = df['Country'].value_counts().reset_index()
    country_counts.columns = ['Country', 'Job Count']
    
    fig_map = px.choropleth(
        country_counts,
        locations="Country",
        locationmode='country names',
        color="Job Count",
        hover_name="Country",
        color_continuous_scale="Viridis",
        title="<b>Geographic Distribution of Labor Demand (Q3-Q4 2025)</b>",
        scope="asia"
    )
    fig_map.update_geos(fitbounds="locations", visible=True)
    fig_map.update_layout(margin={"r":0,"t":50,"l":0,"b":0})
    fig_map.write_html(os.path.join(OUTPUT_DIR, "1_Geographic_Map.html"))

    # ================= 2. SALARY DISPARITY (BOX PLOT) =================
    print("Generating Salary Analysis...")
    salary_df = df[df['Salary_USD_Annual'] > 0].copy()
    # Remove extreme outliers for cleaner visual (e.g. > $300k in low cost regions)
    salary_df = salary_df[salary_df['Salary_USD_Annual'] < 400000]

    fig_sal = px.box(
        salary_df, 
        x="Country", 
        y="Salary_USD_Annual", 
        color="Region",
        points=False, # Don't show all points to keep it clean
        title="<b>Cross-Border Salary Disparity (Annual USD)</b>",
        log_y=True, # Log scale is vital here!
        color_discrete_sequence=colors
    )
    fig_sal.update_layout(yaxis_title="Annual Salary (USD - Log Scale)", xaxis_title="")
    fig_sal.write_html(os.path.join(OUTPUT_DIR, "2_Salary_Disparity.html"))

    # ================= 3. MOST DEMANDED JOBS (TREEMAP) =================
    print("Generating Job Titles Treemap...")
    # Get Top 20 Jobs per Country to avoid clutter
    top_jobs = df.groupby(['Country', 'Job Title']).size().reset_index(name='Count')
    top_jobs = top_jobs.sort_values(['Country', 'Count'], ascending=[True, False]).groupby('Country').head(10)

    fig_tree = px.treemap(
        top_jobs, 
        path=[px.Constant("Asia"), 'Country', 'Job Title'], 
        values='Count',
        color='Country',
        title="<b>Top 10 Most Demanded Roles by Country</b>",
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig_tree.write_html(os.path.join(OUTPUT_DIR, "3_Job_Demand_Treemap.html"))

    # ================= 4. SKILL DEMAND ANALYSIS (BARS) =================
    print("Generating Skills Analysis (This takes a moment)...")
    # Need to split comma separated skills
    skills_series = df['Skills Required'].dropna().str.split(',').explode().str.strip()
    # Remove generic/bad skills
    skills_series = skills_series[~skills_series.isin(['Not Specified', 'nan', 'Null', ''])]
    top_skills = skills_series.value_counts().head(20).reset_index()
    top_skills.columns = ['Skill', 'Count']

    fig_skill = px.bar(
        top_skills, 
        x='Count', 
        y='Skill', 
        orientation='h',
        title="<b>Top 20 Most Requested Skills (Aggregate)</b>",
        text='Count',
        color='Count',
        color_continuous_scale='Magma'
    )
    fig_skill.update_layout(yaxis=dict(autorange="reversed"))
    fig_skill.write_html(os.path.join(OUTPUT_DIR, "4_Top_Skills.html"))

    # ================= 5. HIGHEST PAYING ROLES (SCATTER) =================
    print("Generating High Value Roles...")
    # Group by Job Title, filter for titles with at least 10 postings to avoid noise
    job_stats = salary_df.groupby('Job Title')['Salary_USD_Annual'].agg(['median', 'count']).reset_index()
    job_stats = job_stats[job_stats['count'] > 10].sort_values('median', ascending=False).head(30)

    fig_high = px.scatter(
        job_stats, 
        x='median', 
        y='Job Title', 
        size='count',
        color='median',
        title="<b>Highest Paying Roles (Median Annual USD)</b><br>Size = Hiring Volume",
        color_continuous_scale='Turbo'
    )
    fig_high.update_layout(yaxis=dict(autorange="reversed"), xaxis_title="Median Salary (USD)")
    fig_high.write_html(os.path.join(OUTPUT_DIR, "5_High_Value_Jobs.html"))

    print(f"\n✅ All Interactive Plots saved to: /{OUTPUT_DIR}")
    print("Open these HTML files in Chrome/Safari to show your supervisor.")

if __name__ == "__main__":
    generate_visuals()