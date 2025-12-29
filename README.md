# 🌏 South & Southeast Asian Labor Market Dataset (SSLMD-2025)

![Data Volume](https://img.shields.io/badge/Volume-927k_Records-blue?style=for-the-badge&logo=database)
![Coverage](https://img.shields.io/badge/Coverage-6_Economies-green?style=for-the-badge&logo=googlemaps)
![Timeframe](https://img.shields.io/badge/Timeframe-July_--_Dec_2025-orange?style=for-the-badge&logo=time)
![Format](https://img.shields.io/badge/Format-TSV_(Tab_Separated)-lightgrey?style=for-the-badge)

This project is a high-fidelity, longitudinal study of labor demand across **South and Southeast Asia**. Aggregated via a heterogeneous scraping pipeline, it harmonizes **927,182 job postings** from disparate sources into a unified schema, offering a granular view of cross-border salary disparities, skill demand, and economic shifts.

> **Research Goal:** To bridge the gap between unstructured web data and structured economic indicators for NLP, Econometrics, and AI modeling.

---

## 🚀 Dataset Highlights

### Core Metrics
| Metric | Value | Description |
|:----------|:--------:|:-------------|
| **Total Records** | **927,182** | Post-filtering (July 1, 2025 – Dec 24, 2025) |
| **Salary Transparency** | **32.68%** | Jobs with disclosed wages (303,049 records) |
| **Median Wage (SG)** | **$31,080** | Highest regional baseline (Singapore) |
| **Median Wage (PK)** | **$2,160** | Emerging market baseline (Pakistan) |
| **Tech Stack** | **Hybrid** | GraphQL API + Playwright + Selenium |

### Coverage Map
| Region | Economy | Primary Source | Extraction Method |
|:---|:---|:---|:---|
| 🇸🇬 **Singapore** | High-Income | JobStreet.sg | `GraphQL API` (Reverse Engineered) |
| 🇮🇳 **India** | Service Hub | Naukri.com | `Playwright` (Headless Browser) |
| 🇵🇭 **Philippines** | BPO Leader | JobStreet.ph | `GraphQL API` |
| 🇮🇩 **Indonesia** | G20 Emerging | JobStreet.id | `GraphQL API` |
| 🇵🇰 **Pakistan** | Developing | Rozee.pk | `Requests` (Session) |
| 🇧🇩 **Bangladesh** | Developing | BDJobs.com | `Selenium` |

---

## 📊 Exploratory Data Analysis (EDA)

Detailed interactive charts are available in the [`Interactive_Report/`](./Interactive_Report) directory.

### 1. The Wage Gap (Location Premium)
*Based on Median Annual Salary (Normalized to USD, Q4 2025 Rates)*

The economic disparity is distinct. A role in Singapore commands a **5.7x premium** over the Philippines and a **14.3x premium** over Pakistan.

| Rank | Country | Median Annual Salary | Economic Tier |
|:---:|:---|:---:|:---|
| 🥇 | **Singapore** | **$31,080** | 🟦 High Income / Tech Hub |
| 🥈 | **India** | **$6,000** | 🟩 Global Outsourcing Hub |
| 🥉 | **Philippines** | **$5,400** | 🟩 Service Economy |
| 4 | **Indonesia** | **$3,072** | 🟨 Emerging Market |
| 5 | **Bangladesh** | **$2,295** | 🟧 Developing Market |
| 6 | **Pakistan** | **$2,160** | 🟧 Developing Market |

### 2. Geographic Distribution
*   **Indonesia** dominates the dataset with **279k** postings, signaling rapid digital hiring growth.
*   **India** contributes **85k** high-quality listings, primarily in the Tech/IT sector (Naukri).
*   **Singapore** maintains high volume (**201k**) relative to its population size, indicating a talent shortage.

---

## 🛠️ Schema & Preprocessing

The dataset underwent a rigorous **ETL (Extract, Transform, Load)** process to ensure cross-border comparability.

### The Pipeline (`merge.py`)
1.  **Date Harmonization:** Standardized mixed formats (`Dec 23, 2025` vs `2025-12-16`) into ISO 8601.
2.  **Salary Normalization:**
    *   **Parsing:** Regex handles South Asian multipliers (`Lakh`, `Crore`, `k`).
    *   **Frequency:** *Naukri* data treated as **Annual**; *SE Asia* data treated as **Monthly** (x12).
    *   **Currency:** All converted to USD.
3.  **Deduplication:** Composite key check `{Title, Company, Date, Location}` removed duplicates.

### Column Dictionary
| Column | Type | Description |
|:---|:---|:---|
| `Job ID` | `str` | Unique source identifier |
| `Job Title` | `str` | Standardized role title |
| `Company Name` | `str` | Hiring organization |
| `Posted On` | `datetime` | Publication date |
| `Salary_USD_Annual` | `float` | **Enriched:** Normalized Annual USD Salary |
| `Description` | `str` | Unstructured text (great for NLP) |
| `Region` | `str` | 'South Asia' vs 'South East Asia' |

---

## 🧠 AI & Research Applications

This dataset is optimized for training machine learning models in Labor Economics and HR Tech.

### 🤖 NLP & Taxonomy
*   **Named Entity Recognition (NER):** Extract specific tools (e.g., "TensorFlow") vs Soft Skills (e.g., "Leadership") from the raw `Job Description`.
*   **Role Clustering:** Use **BERTopic** to map variations like "React Dev" and "Frontend Engineer (React)" to a single canonical title.

### 📈 Predictive Modeling
*   **Salary Estimation:**
    *   *Input:* Location + Experience + Title
    *   *Target:* `Salary_USD_Annual`
    *   *Goal:* Build a "Fair Pay" calculator for remote workers.
*   **Economic Forecasting:** Use job posting velocity as a proxy for real-time GDP growth (Nowcasting).

---

## 📖 Quick Start

### 1. Load the Data
```python
import pandas as pd

# Load with tab separator
df = pd.read_csv("Dataset(TSV)/Final_SSLMD_2025.tsv", sep='\t', low_memory=False)

# Convert dates
df['Posted On'] = pd.to_datetime(df['Posted On'])

# View high-paying jobs in India
print(df[(df['Country'] == 'India') & (df['Salary_USD_Annual'] > 50000)].head())