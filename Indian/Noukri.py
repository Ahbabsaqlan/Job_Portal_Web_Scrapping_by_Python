#!/usr/bin/env python3
import os
import logging
import requests
import pandas as pd
import math
import re
import json
import time
import random
import warnings
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

# --- NEW IMPORTS ---
from playwright.sync_api import sync_playwright 
# -------------------

# ================= CONFIGURATION ================= #
BASE_DIR = "/Users/jihan/JobWebScrapper"
MASTER_FILE = os.path.join(BASE_DIR, "Dataset/naukri_master_data.xlsx")
LOG_DIR = os.path.join(BASE_DIR, "logs")
SUMMARY_FILE = os.path.join(BASE_DIR, "run_summary.json")
SEARCH_URL = "https://www.naukri.com/jobapi/v3/search"
SEARCH_KEYWORD = "indian portal"
SEO_KEY_BASE = "indian-portal-jobs"
PAGE_SIZE = 20
NEW_JOB_TARGET = 10000
REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
RETRY_BACKOFF = 1

# ================= SETUP ================= #
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = datetime.now().strftime("naukri_run_%Y-%m-%d_%H-%M.log")
log_path = os.path.join(LOG_DIR, log_filename)

# Reset logging handlers
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)

# ================= HELPER FUNCTIONS ================= #
def clean_text_for_excel(text):
    if not isinstance(text, str): return text
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

def save_run_summary(scraper_name, summary_data):
    """Saves execution statistics to a JSON file."""
    try:
        all_summaries = {}
        if os.path.exists(SUMMARY_FILE):
            with open(SUMMARY_FILE, 'r') as f: 
                try:
                    all_summaries = json.load(f)
                except json.JSONDecodeError:
                    all_summaries = {}
        
        all_summaries[scraper_name] = summary_data
        
        with open(SUMMARY_FILE, 'w') as f: 
            json.dump(all_summaries, f, indent=4)
            
        logging.info(f"✅ Saved run summary for {scraper_name}")
    except Exception as e:
        logging.error(f"❌ Failed to save run summary: {e}")

def save_to_master(new_data):
    if not new_data: return 0
    df_new = pd.DataFrame(new_data)
    try:
        df_old = pd.DataFrame()
        if os.path.exists(MASTER_FILE):
            df_old = pd.read_excel(MASTER_FILE, engine="openpyxl", dtype={'Job ID': str})
        
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        # Clean IDs
        df_combined['Job ID'] = df_combined['Job ID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df_combined.drop_duplicates(subset=["Job ID"], keep="last", inplace=True)
        
        df_combined.to_excel(MASTER_FILE, index=False, engine='openpyxl')
        logging.info(f"✅ Master file updated. Total unique jobs: {len(df_combined)}")
        return len(df_combined)
    except Exception as e:
        logging.error(f"❌ SAVE FAILED: {e}")
        return -1

def create_session_with_retries():
    session = requests.Session()
    retry_strategy = Retry(total=RETRY_COUNT, backoff_factor=RETRY_BACKOFF, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def get_search_headers(search_url, nkparam_token):
    # Fallback token
    token = nkparam_token if nkparam_token else "Wk0YSMCWWVyMfwNhQgrljvm3Z2/eg+wQPZymeUbeBEfKf6Z0CFJbzBfMSd1fp4kPZSmRwNtYOeV01WWmIl3k5A=="
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "appid": "109",
        "systemid": "Naukri",
        "clientid": "d3skt0p",
        "gid": "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
        "nkparam": token,
        "Referer": search_url
    }

# ================= STEP 1: EXTRACT SEARCH TOKEN ================= #
def extract_naukri_nkparam():
    """
    Extracts nkparam for the Search API (v3).
    Runs visibly (headless=False) to bypass bot checks.
    """
    target_api_url_part = '/jobapi/v3/search'
    start_url = f"https://www.naukri.com/{SEO_KEY_BASE}" 
    nkparam_value = None
    logging.info("🔑 Attempting to extract dynamic SEARCH nkparam token...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False, 
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            try:
                with page.expect_request(lambda request: target_api_url_part in request.url, timeout=20000) as request_info:
                    page.goto(start_url, wait_until="domcontentloaded")
                
                target_request = request_info.value
                headers = target_request.all_headers()
                nkparam_value = headers.get('nkparam')
                
                if nkparam_value:
                    logging.info("✅ Successfully extracted SEARCH nkparam.")
                else:
                    logging.warning("⚠️ Request found but nkparam header missing.")
                    
            except Exception as e:
                logging.warning(f"⚠️ Search token extraction timed out (Using fallback): {e}")
            
            browser.close()
            return nkparam_value
    except Exception as e:
        logging.critical(f"❌ Playwright launch failed: {e}")
        return None

# ================= STEP 2: COLLECT IDs (REQUESTS) ================= #
def collect_new_job_ids(session, existing_ids, search_token):
    logging.info(f"--- Starting ID Collection: aiming for {NEW_JOB_TARGET} new jobs ---")
    headers = get_search_headers(f"https://www.naukri.com/{SEO_KEY_BASE}", search_token)
    newly_found_ids = set()
    issues = []
    
    try:
        params = {'noOfResults': PAGE_SIZE, 'urlType': 'search_by_keyword', 'searchType': 'adv', 'keyword': SEARCH_KEYWORD, 'pageNo': 1, 'seoKey': SEO_KEY_BASE}
        resp = session.get(SEARCH_URL, headers=headers, params=params, timeout=10)
        
        if resp.status_code != 200:
            msg = f"Search API returned {resp.status_code}. Token might be bad."
            logging.error(msg)
            issues.append(msg)
            return [], issues

        data = resp.json()
        total_jobs = data.get('noOfJobs', 0)
        total_pages = math.ceil(total_jobs / PAGE_SIZE)
        logging.info(f"API reports {total_jobs} total jobs.")
        
        for page in tqdm(range(1, total_pages + 1), desc="Collecting IDs"):
            if page > 1:
                params['pageNo'] = page
                try:
                    resp = session.get(SEARCH_URL, headers=headers, params=params, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                    else:
                        continue
                except:
                    continue
            
            ids_on_page = {str(job['jobId']).strip() for job in data.get("jobDetails", []) if 'jobId' in job}
            ids_on_page = {jid for jid in ids_on_page if jid != ""}
            unique_ids = {id for id in ids_on_page if id not in existing_ids}
            newly_found_ids.update(unique_ids)
            
            if len(newly_found_ids) >= NEW_JOB_TARGET:
                logging.info(f"Target of {NEW_JOB_TARGET} new jobs reached.")
                break
            
            time.sleep(random.uniform(0.5, 1.0)) 
            
    except Exception as e:
        msg = f"ID Collection failed: {e}"
        logging.error(msg)
        issues.append(msg)
        
    return list(newly_found_ids)[:NEW_JOB_TARGET], issues

# ================= STEP 3: SCRAPE DETAILS (VISIBLE BROWSER) ================= #
def scrape_details_with_browser(job_ids):
    scraped_data = []
    
    logging.info("🚀 Launching Browser for Detail Scraping (Visible Mode)...")
    
    with sync_playwright() as p:
        # Launch browser visibly to bypass bot detection
        browser = p.chromium.launch(
            headless=False, # <--- MUST BE FALSE
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        
        page = context.new_page()

        for job_id in tqdm(job_ids, desc="Scraping Details"):
            web_url = f"https://www.naukri.com/job-listings-{job_id}"
            
            try:
                # We expect a JSON response from the API
                # Using a broad filter to catch v3 or v4 API calls
                with page.expect_response(lambda r: "jobapi" in r.url and "job" in r.url and r.status == 200, timeout=10000) as response_info:
                    page.goto(web_url, wait_until="domcontentloaded")
                
                # Get the JSON
                raw_json = response_info.value.json()
                
                # Parse
                if "jobDetails" in raw_json:
                    details = raw_json["jobDetails"]
                    
                    # Clean Description
                    raw_desc = details.get("description", "")
                    soup = BeautifulSoup(raw_desc, 'html.parser')
                    description = clean_text_for_excel(soup.get_text(separator='\n', strip=True))
                    
                    # Skills
                    skills = []
                    if "keySkills" in details:
                        for cat in ["preferred", "other"]:
                            if cat in details["keySkills"]:
                                skills.extend([s.get("label") for s in details["keySkills"][cat] if isinstance(s, dict)])
                    
                    # Locations
                    locs = [l.get("label") for l in details.get("locations", []) if isinstance(l, dict)]
                    
                    row = {
                        "Job ID": str(details.get("jobId", job_id)).strip(), 
                        "Job Title": clean_text_for_excel(details.get("title", "")), 
                        "Company Name": clean_text_for_excel(details.get("companyDetail", {}).get("name", "")), 
                        "Posted On": details.get("createdDate", ""), 
                        "Vacancies": details.get("vacancy", 1), 
                        "Location": ", ".join(locs), 
                        "Salary Range": details.get("salaryDetail", {}).get("label", "Not disclosed"), 
                        "Job Description": description, 
                        "Experience": details.get("experienceText", ""), 
                        "Skills Required": ", ".join(skills), 
                        "Job Link": details.get("staticUrl", web_url)
                    }
                    scraped_data.append(row)
                
            except Exception as e:
                # logging.warning(f"❌ Failed {job_id}: {e}")
                pass
            
            # Random delay to mimic human behavior
            time.sleep(random.uniform(1.0, 3.0))
            
        browser.close()
        
    return scraped_data

# ================= MAIN ================= #
def main():
    logging.info("🚀 Script Started")
    issues = []
    newly_added = 0
    new_total = 0
    existing_count = 0
    
    try:
        # 1. Get Search Token
        search_token = extract_naukri_nkparam()
        if not search_token:
            issues.append("Search Token Extraction Failed (Used Fallback)")
        
        # 2. Setup Requests Session
        session = create_session_with_retries()
        
        # 3. Load Existing IDs
        if not os.path.exists(MASTER_FILE):
            existing_ids = set()
        else:
            try:
                df = pd.read_excel(MASTER_FILE, engine="openpyxl", dtype={'Job ID': str})
                existing_ids = set(df['Job ID'].astype(str).str.replace(r'\.0$', '', regex=True).tolist())
            except Exception as e:
                existing_ids = set()
                issues.append(f"Failed to load master file: {e}")
        
        existing_count = len(existing_ids)
        logging.info(f"Loaded {existing_count} existing jobs.")
        
        # 4. Collect New IDs
        new_ids, collection_issues = collect_new_job_ids(session, existing_ids, search_token)
        issues.extend(collection_issues)
        
        if not new_ids:
            logging.info("No new jobs found.")
            status = "No New Jobs"
        else:
            logging.info(f"🔍 Found {len(new_ids)} new jobs. Launching detail scraper...")
            
            # 5. Scrape Details (Visible Browser)
            final_data = scrape_details_with_browser(new_ids)
            newly_added = len(final_data)
            
            # 6. Save
            if final_data:
                new_total = save_to_master(final_data)
                if new_total == -1:
                    status = "Save Failed"
                    issues.append("Could not save data to master file")
                    new_total = existing_count
                else:
                    status = "Completed"
            else:
                status = "Completed (No Details)"
                new_total = existing_count
                issues.append("Scraping finished but no details were captured (Check bot detection)")

        # 7. Summary
        summary = {
            "status": status,
            "existing_jobs": existing_count,
            "newly_added": newly_added,
            "new_total": new_total if new_total > 0 else existing_count,
            "issues": issues
        }
        save_run_summary("Noukri.com", summary)
        
    except Exception as e:
        logging.critical(f"Global Crash: {e}", exc_info=True)
        summary = {
            "status": "Crashed",
            "existing_jobs": existing_count,
            "newly_added": 0,
            "new_total": existing_count,
            "issues": issues + [f"Script Crashed: {str(e)}"]
        }
        save_run_summary("Noukri.com", summary)

if __name__ == "__main__":
    main()