#!/usr/bin/env python3
import os
import logging
import requests
import pandas as pd
import re
import json
import time
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm # <-- Ensure tqdm is imported

# ... (CONFIGURATION and LOGGING SETUP remain the same) ...
# ================= CONFIGURATION ================= #
BASE_DIR = "/Users/jihan/JobData"
MASTER_FILE = os.path.join(BASE_DIR, "rozee_master_data.xlsx")
LOG_DIR = os.path.join(BASE_DIR, "logs")
SUMMARY_FILE = os.path.join(BASE_DIR, "run_summary.json")

# --- Rozee.pk Params ---
BASE_SEARCH_URL = "https://www.rozee.pk/job/jsearch/q/all"
PAGE_SIZE = 20
REQUEST_DELAY = 0.3
NEW_JOB_TARGET = 10000
REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
RETRY_BACKOFF = 1

# ================= LOGGING SETUP ================= #
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = datetime.now().strftime("rozee_run_%Y-%m-%d_%H-%M.log")
log_path = os.path.join(LOG_DIR, log_filename)
logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)

# ... (HELPER FUNCTIONS like save_run_summary, fetch_job_details, etc. remain the same) ...
def save_run_summary(scraper_name, summary_data):
    try:
        all_summaries = {}
        if os.path.exists(SUMMARY_FILE):
            with open(SUMMARY_FILE, 'r') as f:
                all_summaries = json.load(f)
        all_summaries[scraper_name] = summary_data
        with open(SUMMARY_FILE, 'w') as f:
            json.dump(all_summaries, f, indent=4)
        logging.info(f"✅ Saved run summary for {scraper_name}")
    except Exception as e:
        logging.error(f"❌ Failed to save run summary: {e}")
def create_session_with_retries():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    retry_strategy = Retry(total=RETRY_COUNT, backoff_factor=RETRY_BACKOFF, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter); session.mount("http://", adapter)
    return session
def clean_text_for_excel(text):
    if not isinstance(text, str): return text
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
def parse_rozee_page(page_content):
    match = re.search(r"var apResp = (\{.*?\});", page_content, re.DOTALL)
    try: return json.loads(match.group(1)) if match else None
    except json.JSONDecodeError: return None
def extract_job_details_from_apresp(job_dict):
    return {"Job ID": str(job_dict.get("jid")), "Job Title": clean_text_for_excel(job_dict.get("title")), "Company Name": clean_text_for_excel(job_dict.get("company_name")), "Posted On": job_dict.get("displayDate", "").split(" ")[0], "City": job_dict.get("city"), "Experience Required": job_dict.get("experience_text"), "Skills Required": ", ".join(job_dict.get("skills", [])), "Job Type": job_dict.get("type"), "Min Salary": job_dict.get("salaryN_exact"), "Max Salary": job_dict.get("salaryT_exact"), "Job Description Snippet": clean_text_for_excel(job_dict.get("description")), "Job Link": f"https://www.rozee.pk/{job_dict.get('rozeePermaLink')}"}
def load_existing_job_ids():
    if not os.path.exists(MASTER_FILE): return set()
    try: return set(pd.read_excel(MASTER_FILE, engine="openpyxl")["Job ID"].astype(str).tolist())
    except Exception as e: logging.error(f"❌ Could not read master file: {e}"); return set()
def save_to_master(new_data):
    if not new_data: return 0
    df_new = pd.DataFrame(new_data)
    final_cols = ["Job ID", "Job Title", "Company Name", "Posted On", "City", "Experience Required", "Skills Required", "Job Type", "Min Salary", "Max Salary", "Job Description Snippet", "Job Link"]
    for col in final_cols:
        if col not in df_new.columns: df_new[col] = None
    df_new = df_new[final_cols]
    try:
        if os.path.exists(MASTER_FILE):
            df_old = pd.read_excel(MASTER_FILE, engine="openpyxl")
            df_old['Job ID'], df_new['Job ID'] = df_old['Job ID'].astype(str), df_new['Job ID'].astype(str)
            df_combined = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates(subset=["Job ID"], keep="last")
        else: df_combined = df_new
        df_combined.to_excel(MASTER_FILE, index=False, engine='openpyxl')
        logging.info(f"✅ Master file updated. Total unique jobs: {len(df_combined)}")
        return len(df_combined)
    except Exception as e: logging.error(f"❌ SAVE FAILED: {e}", exc_info=True); return -1


def collect_new_rozee_jobs(session, existing_ids):
    new_jobs_data, newly_found_ids, issues = [], set(), []
    page_num = 1
    # MODIFIED: Using tqdm directly as a context manager is cleaner
    with tqdm(total=NEW_JOB_TARGET, desc="Finding new Rozee.pk jobs") as pbar:
        while len(new_jobs_data) < NEW_JOB_TARGET:
            offset = (page_num - 1) * PAGE_SIZE
            page_url = BASE_SEARCH_URL if offset == 0 else f"{BASE_SEARCH_URL}/fpn/{offset}"
            try:
                resp = session.get(page_url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                page_data = parse_rozee_page(resp.text)
                if not page_data:
                    issues.append(f"Failed to parse page {page_num}. May be an anti-bot block.")
                    if len(issues) > 5 and "Stopping collection" not in issues[-1]:
                        issues.append("Stopping collection due to multiple consecutive page parse failures.")
                        break
                    page_num += 1
                    continue
                
                jobs_on_page = page_data.get("response", {}).get("jobs", {}).get("sponsored", []) + page_data.get("response", {}).get("jobs", {}).get("basic", [])
                if not jobs_on_page:
                    logging.info(f"  → No jobs found on page {page_num}. Assuming end of listings.")
                    break
                
                for job_dict in jobs_on_page:
                    job_id = str(job_dict.get("jid"))
                    if job_id and job_id not in existing_ids and job_id not in newly_found_ids:
                        newly_found_ids.add(job_id)
                        new_jobs_data.append(extract_job_details_from_apresp(job_dict))
                        pbar.update(1)
                        if len(new_jobs_data) >= NEW_JOB_TARGET: break
                
                if len(new_jobs_data) >= NEW_JOB_TARGET: break
                page_num += 1
                time.sleep(REQUEST_DELAY)
                
            except requests.exceptions.RequestException as e:
                issues.append(f"Network error on page {page_num}, stopping collection: {e}")
                break
                
    return new_jobs_data[:NEW_JOB_TARGET], issues

# ================= MAIN SCRAPER LOGIC ================= #
def main():
    # ... (main function is identical to the one in the previous response, with issue tracking) ...
    logging.info("🚀 Rozee.pk Scraper Started")
    session = create_session_with_retries()
    
    existing_ids = load_existing_job_ids()
    existing_count = len(existing_ids)
    
    new_jobs_to_save, issues = collect_new_rozee_jobs(session, existing_ids)
    
    newly_added_count, new_total_count = 0, existing_count
    status = "Completed"
    if not new_jobs_to_save:
        status = "No new jobs"
        if issues: status = "Collection Failed"
    else:
        new_total_count = save_to_master(new_jobs_to_save)
        if new_total_count != -1:
            newly_added_count = len(new_jobs_to_save)
            if issues: status = "Completed with issues"
        else:
            status = "Save Failed"
            issues.append("Critical error: Failed to save data to master file.")
            new_total_count = existing_count
    
    summary = {"status": status, "existing_jobs": existing_count, "newly_added": newly_added_count, "new_total": new_total_count, "issues": issues}
    save_run_summary("Rozee.pk", summary)
    logging.info("🏁 Rozee.pk Scraper finished.")

# ... (Crash handler remains the same) ...
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"💥 Rozee.pk Global crash: {e}", exc_info=True)
        existing_count = len(load_existing_job_ids())
        summary = {"status": "Crashed", "existing_jobs": existing_count, "newly_added": 0, "new_total": existing_count, "issues": [f"Fatal script error: {e}"]}
        save_run_summary("Rozee.pk", summary)