import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- Step 1: Load Excel ---
df = pd.read_excel("naukri_master_data.xlsx")

# --- Step 2: Ensure 'Posted On' is datetime ---
df['Posted On'] = pd.to_datetime(df['Posted On'], errors='coerce')

# --- Step 3: Extract Year and Year-Month ---
df['Year'] = df['Posted On'].dt.year
df['YearMonth'] = df['Posted On'].dt.to_period('M').astype(str)

# --- Step 4: Function to aggregate counts by Year(s) ---
def get_monthly_counts(years):
    temp = df[df['Year'].isin(years)]
    monthly_counts = temp['YearMonth'].value_counts().sort_index()
    return monthly_counts.rename_axis('YearMonth').reset_index(name='Posts')

# --- Step 5: Prepare data for each view ---
all_years = get_monthly_counts([2024, 2025])
only_2024 = get_monthly_counts([2024])
only_2025 = get_monthly_counts([2025])

# --- Step 6: Create initial figure (All Years) ---
fig = px.bar(
    all_years,
    x="YearMonth",
    y="Posts",
    text="Posts",
    color="Posts",
    color_continuous_scale=px.colors.sequential.Viridis,
)

fig.update_traces(textposition='outside')

# --- Step 7: Add Dropdown Menu ---
fig.update_layout(
    title="📊 Monthly Job Posting Trends",
    xaxis_title="Month",
    yaxis_title="Number of Job Posts (log scale)",
    yaxis_type="log",
    title_font=dict(size=22, family="Arial Black"),
    plot_bgcolor="white",
    xaxis=dict(showgrid=False),
    yaxis=dict(showgrid=True, gridcolor="lightgrey"),
    updatemenus=[
        dict(
            buttons=list([
                dict(label="All Years",
                     method="update",
                     args=[{"x": [all_years["YearMonth"]],
                            "y": [all_years["Posts"]],
                            "text": [all_years["Posts"]],
                            "marker": {"color": all_years["Posts"],
                                       "colorscale": "Viridis"}}]),
                dict(label="2024",
                     method="update",
                     args=[{"x": [only_2024["YearMonth"]],
                            "y": [only_2024["Posts"]],
                            "text": [only_2024["Posts"]],
                            "marker": {"color": only_2024["Posts"],
                                       "colorscale": "Viridis"}}]),
                dict(label="2025",
                     method="update",
                     args=[{"x": [only_2025["YearMonth"]],
                            "y": [only_2025["Posts"]],
                            "text": [only_2025["Posts"]],
                            "marker": {"color": only_2025["Posts"],
                                       "colorscale": "Viridis"}}]),
            ]),
            direction="down",
            showactive=True,
            x=0.5, y=1.20,
            xanchor="left", yanchor="top"
        )
    ]
)

fig.show()
