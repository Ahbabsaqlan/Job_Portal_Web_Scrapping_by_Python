#!/usr/bin/env python3
import os
import time
import json
import logging
import requests
import pandas as pd
import math
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from collections import defaultdict
from tqdm import tqdm

# ================= CONFIGURATION: SINGAPORE (SG) ================= #
BASE_DIR = "/Users/jihan/JobData"
LOG_DIR = os.path.join(BASE_DIR, "logs")
SUMMARY_FILE = os.path.join(BASE_DIR, "run_summary.json")

# --- Country-Specific Settings ---
HOST = "https://sg.jobstreet.com"
SITE_KEY = "SG-Main"
LOCALE = "en-SG"
TIMEZONE = "Asia/Singapore"
MASTER_FILE = os.path.join(BASE_DIR, "jobstreet_sg_master_data.xlsx")
LOG_FILE_PREFIX = "jobstreet_sg_run"
DISPLAY_NAME = "JobStreet (SG)"
CLASSIFICATIONS = "1200,6251,6304,1203,1204,7019,6163,1206,6076,6263,6123,1209,6205,1210,1211,1212,6317,6281,1214,1216,6092,6008,1225,6246,6261,1223,6362,6043,1220,6058"
API_HEADERS = { "seek-request-brand": "jobstreet", "seek-request-country": "SG", "X-Seek-Site": "chalice" }

# --- API Endpoints & Params ---
ID_SEARCH_URL = "https://jobsearch-api.cloud.seek.com.au/v5/search"
DETAILS_API_URL = f"{HOST}/graphql"
PAGE_SIZE = 100
REQUEST_DELAY = 0.4
PROCESS_LIMIT = 3400

# ================= LOGGING & HELPER FUNCTIONS ================= #
def setup_logging(log_file_prefix):
    os.makedirs(LOG_DIR, exist_ok=True)
    log_filename = os.path.join(LOG_DIR, datetime.now().strftime(f"{log_file_prefix}_%Y-%m-%d_%H-%M.log"))
    for handler in logging.root.handlers[:]: logging.root.removeHandler(handler)
    logging.basicConfig(filename=log_filename, level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)

def save_run_summary(scraper_name, summary_data):
    try:
        all_summaries = {}
        if os.path.exists(SUMMARY_FILE):
            with open(SUMMARY_FILE, 'r') as f: all_summaries = json.load(f)
        all_summaries[scraper_name] = summary_data
        with open(SUMMARY_FILE, 'w') as f: json.dump(all_summaries, f, indent=4)
        logging.info(f"✅ Saved run summary for {scraper_name}")
    except Exception as e: logging.error(f"❌ Failed to save run summary: {e}")

def parse_relative_date(relative_str):
    if not isinstance(relative_str, str): return None
    now = datetime.now(); relative_str = relative_str.lower().strip()
    if 'just now' in relative_str or 'today' in relative_str: return now.strftime('%Y-%m-%d')
    if 'yesterday' in relative_str: return (now - timedelta(days=1)).strftime('%Y-%m-%d')
    match = re.search(r'(\d+)\s*([dhwm])', relative_str)
    if not match: return relative_str
    value, unit = int(match.group(1)), match.group(2)
    delta = {'d': timedelta(days=value), 'h': timedelta(hours=value), 'w': timedelta(weeks=value)}.get(unit, timedelta(days=0))
    return (now - delta).strftime('%Y-%m-%d')

def safe_get(dictionary, keys, default=None):
    if not isinstance(dictionary, dict): return default
    current = dictionary
    for key in keys:
        if isinstance(current, dict) and key in current and current[key] is not None: current = current[key]
        else: return default
    return current

# ============================ NEW HELPER FUNCTION ============================
def clean_excel_string(value):
    """Sanitizes a string to remove characters that are illegal in Excel worksheets."""
    if not isinstance(value, str):
        return value
    return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', value)
# ============================================================================

def final_robust_parser(html_content):
    if not html_content: return {}
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup.select('style, script, meta, link, img'): tag.decompose()
        results, current_header, seen_content = defaultdict(list), "Job Description", set()
        for element in soup.find_all(['h1', 'h2', 'h3', 'p', 'ul', 'ol']):
            header_text = None
            if element.name in ['h1', 'h2', 'h3']: header_text = element.get_text(strip=True)
            elif element.name == 'p':
                if element.find(['strong', 'b']) or element.get_text(strip=True).endswith(':'): header_text = element.get_text(strip=True).rstrip(':')
                else:
                    text = element.get_text(strip=True)
                    if text and text not in seen_content: seen_content.add(text); results[current_header].append(text)
            elif element.name in ['ul', 'ol']:
                for li in element.find_all('li'):
                    li_text = li.get_text(strip=True)
                    if li_text and li_text not in seen_content: seen_content.add(li_text); results[current_header].append(li_text)
            if header_text: current_header = header_text
        return dict(results)
    except Exception as e: logging.error(f"❌ Error in final_robust_parser: {e}", exc_info=True); return {}

def standardize_column_names(name):
    clean = name.lower().replace(':', '').strip()
    mapping = {'job description|responsibilities|duties|role': 'Job Description', 'requirements|requisite|what you bring': 'Additional Requirements', 'skills|competencies|knowledge': 'Skills Required', 'qualifications|education': 'Education Requirements', 'experience': 'Experience'}
    for p, s in mapping.items():
        if re.search(p, clean): return s
    return name

def fetch_job_details(job_id):
    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "Origin": HOST}
    headers.update(API_HEADERS)
    payload = {"operationName": "JobDetails", "variables": {"jobId": job_id, "locale": LOCALE, "timezone": TIMEZONE, "languageCode": "en"}, "query": "query JobDetails($jobId: ID!, $locale: Locale!, $timezone: Timezone!, $languageCode: LanguageCodeIso!) { jobDetails(id: $jobId) { job { id title advertiser { name } salary { label } location { label } listedAt { label(context: JOB_POSTED, length: SHORT, timezone: $timezone, locale: $locale) } classifications { label(languageCode: $languageCode) } content } } }"}
    try:
        resp = requests.post(DETAILS_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        try: data = resp.json()
        except json.JSONDecodeError: logging.warning(f"⚠️ Failed to decode JSON for job {job_id}. Skipping."); return None
        job_details = safe_get(data, ['data', 'jobDetails', 'job'], {})
        if not job_details: logging.warning(f"⚠️ No valid job data in API response for job {job_id}. Skipping."); return None
        final_record = {
            "Job ID": str(job_details.get('id')), "Job Title": job_details.get('title'),
            "Company Name": safe_get(job_details, ['advertiser', 'name']), "Posted On": parse_relative_date(safe_get(job_details, ['listedAt', 'label'])),
            "Job Nature": safe_get(job_details, ['classifications', 0, 'label']), "Location": safe_get(job_details, ['location', 'label']),
            "Salary Range": safe_get(job_details, ['salary', 'label']), "Job Link": f"{HOST}/job/{job_details.get('id')}"
        }
        
        parsed_content = final_robust_parser(job_details.get('content', ''))
        
        
        list_based_columns = ['Job Description', 'Additional Requirements', 'Skills Required', 'Education Requirements', 'Experience']
        final_record.update({col: [] for col in list_based_columns})
        
        unmapped = []
        for h, c_list in parsed_content.items():
            key = standardize_column_names(h)
            if key in list_based_columns:
                final_record[key].extend(c_list)
            else:
                unmapped.extend([f"{h}:"] + c_list)
        if unmapped:
            final_record['Job Description'].extend(unmapped)
            
        return final_record
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Network error processing job {job_id}: {e}", exc_info=False)
        return None
    except Exception as e:
        # Changed the log message to be more specific about the error source
        logging.error(f"❌ Error processing job details for {job_id}: {e}", exc_info=True)
        return None

def load_existing_job_ids():
    if not os.path.exists(MASTER_FILE): return set()
    try:
        df = pd.read_excel(MASTER_FILE, engine="openpyxl", dtype={'Job ID': str})
        if "Job ID" not in df.columns or df.empty: return set()
        id_series = df["Job ID"].dropna().astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        return set(id_series[id_series != ""].tolist())
    except Exception as e: logging.error(f"❌ Could not read master file {MASTER_FILE}: {e}"); return set()

def save_to_master(new_data):
    if not new_data: return 0
    df_new = pd.DataFrame(new_data)
    final_cols = ["Job ID", "Job Title", "Company Name", "Posted On", "Deadline", "Vacancies", "Job Nature", "Workplace", "Location", "Salary Range", "Job Description", "Education Requirements", "Experience", "Additional Requirements", "Skills Required", "Company Address", "Apply Email", "Apply Instruction", "Job Link"]
    for col in final_cols:
        if col not in df_new.columns: df_new[col] = None
    df_new = df_new[final_cols]
    
    list_columns = ["Job Description", "Education Requirements", "Experience", "Additional Requirements", "Skills Required"]
    delimiter = "; "
    for col in list_columns:
        if col in df_new.columns:
            df_new[col] = df_new[col].apply(lambda x: delimiter.join(x) if isinstance(x, list) else x)

    EXCEL_CHAR_LIMIT = 32750
    text_columns_to_truncate = list_columns + ["Apply Instruction"]
    truncation_suffix = "... [TRUNCATED]"
    for col in text_columns_to_truncate:
        if col in df_new.columns:
            df_new[col] = df_new[col].apply(lambda x: (x[:EXCEL_CHAR_LIMIT - len(truncation_suffix)] + truncation_suffix) if isinstance(x, str) and len(x) > EXCEL_CHAR_LIMIT else x)

    try:
        df_old = pd.DataFrame(columns=final_cols)
        if os.path.exists(MASTER_FILE):
            df_old = pd.read_excel(MASTER_FILE, engine="openpyxl", dtype={'Job ID': str})
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        df_combined['Job ID'] = df_combined['Job ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df_combined = df_combined[df_combined['Job ID'].notna() & (df_combined['Job ID'] != "")].copy()
        df_combined.drop_duplicates(subset=["Job ID"], keep="last", inplace=True)
        
        # ======================= FIX: SANITIZE ALL DATA =======================
        df_combined = df_combined.applymap(clean_excel_string)
        # =====================================================================
        
        df_combined.to_excel(MASTER_FILE, index=False, engine='openpyxl')
        logging.info(f"✅ Master file updated. Total unique jobs: {len(df_combined)}")
        return len(df_combined)
    except Exception as e: logging.error(f"❌ SAVE FAILED: {e}", exc_info=True); return -1

def collect_new_jobstreet_ids_until_target_met(existing_ids, target_count):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    newly_found_ids, issues = set(), []
    try:
        params = {"siteKey": SITE_KEY, "page": 1, "pageSize": PAGE_SIZE, "classification": CLASSIFICATIONS}
        resp = requests.get(ID_SEARCH_URL, headers=headers, params=params, timeout=20)
        resp.raise_for_status(); data = resp.json()
        total_jobs = data.get('totalCount', 0)
        if total_jobs == 0: return [], ["ID Collection: API reported 0 total jobs."]
        total_pages = math.ceil(total_jobs / PAGE_SIZE)
        logging.info(f"API reports {total_jobs} total jobs for {DISPLAY_NAME} across a maximum of {total_pages} pages.")
        
        for page in tqdm(range(1, total_pages + 1), desc=f"Collecting new {DISPLAY_NAME} IDs"):
            if page > 1:
                params['page'] = page
                try:
                    resp = requests.get(ID_SEARCH_URL, headers=headers, params=params, timeout=20)
                    resp.raise_for_status(); data = resp.json()
                except Exception as e: issues.append(f"Failed to fetch ID page {page}: {e}"); continue
            ids_on_page = {str(job.get("id")) for job in data.get("data", []) if job.get("id")}
            unique_to_page = {jid for jid in ids_on_page if jid not in existing_ids}
            newly_found_ids.update(unique_to_page)
            if len(newly_found_ids) >= target_count:
                logging.info(f"✅ Target of {target_count} new jobs reached. Halting ID collection.")
                break
    except Exception as e:
        issues.append(f"Critical ID Collection failure: {e}")
        logging.critical(f"❌ ID Collection failed critically: {e}", exc_info=True)
        return [], issues
    return list(newly_found_ids)[:target_count], issues

def main():
    setup_logging(LOG_FILE_PREFIX)
    logging.info(f"🚀 JobStreet Scraper started for {DISPLAY_NAME}")
    existing_ids = load_existing_job_ids()
    existing_count = len(existing_ids)
    new_job_ids, issues = collect_new_jobstreet_ids_until_target_met(existing_ids, PROCESS_LIMIT)
    logging.info(f"🆕 New jobs to scrape: {len(new_job_ids)}")
    if not new_job_ids:
        summary = {"status": "No new jobs", "existing_jobs": existing_count, "newly_added": 0, "new_total": existing_count, "issues": issues}
        save_run_summary(DISPLAY_NAME, summary); return
    scraped_data, failed_job_scrapes = [], 0
    jobs_to_scrape = new_job_ids
    for job_id in tqdm(jobs_to_scrape, desc=f"Scraping {DISPLAY_NAME} Details"):
        job_details = fetch_job_details(job_id)
        if job_details: scraped_data.append(job_details)
        else: failed_job_scrapes += 1
        time.sleep(REQUEST_DELAY)
    if failed_job_scrapes > 0: issues.append(f"Failed to fetch details for {failed_job_scrapes} out of {len(jobs_to_scrape)} attempted scrapes.")
    newly_added_count, new_total_count, status = 0, existing_count, "Completed"
    if scraped_data:
        new_total_count = save_to_master(scraped_data)
        if new_total_count != -1:
            newly_added_count = len(scraped_data)
            if issues: status = "Completed with issues"
        else: status = "Save Failed"; issues.append("Critical error: Failed to save data to master file."); new_total_count = existing_count
    elif issues: status = "Failed"
    summary = {"status": status, "existing_jobs": existing_count, "newly_added": newly_added_count, "new_total": new_total_count, "issues": issues}
    save_run_summary(DISPLAY_NAME, summary)
    logging.info(f"🏁 JobStreet Scraper for {DISPLAY_NAME} finished.")

if __name__ == "__main__":
    try: main()
    except Exception as e:
        setup_logging(LOG_FILE_PREFIX)
        logging.critical(f"💥 {DISPLAY_NAME} Global crash: {e}", exc_info=True)
        existing_count = len(load_existing_job_ids())
        summary = {"status": "Crashed", "existing_jobs": existing_count, "newly_added": 0, "new_total": existing_count, "issues": [f"Fatal script error: {e}"]}
        save_run_summary(DISPLAY_NAME, summary)