#!/usr/bin/env python3
import os
import time
import json
import logging
import requests
import pandas as pd
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from datetime import datetime
from tqdm import tqdm
import warnings

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

# ================= CONFIGURATION ================= #
BASE_DIR = "/Users/jihan/JobWebScrapper"

# You can keep 55, but API response shows totalpages=90.
# If you want to always scrape all pages, set PAGES_TO_SCRAPE = None and use totalpages from API.
PAGES_TO_SCRAPE = 55
JOBS_PER_PAGE = 100

# 🔥 Job list API (IDs come from here)
JOB_SEARCH_API_TEMPLATE = (
    "https://api.bdjobs.com/Jobs/api/JobSearch/GetJobSearch"
    "?Icat=&industry=&category=&org=&jobNature=&Fcat=&location=&Qot=&jobType=&jobLevel=&postedWithin=&deadline=&keyword="
    "&pg={pg}&qAge=&Salary=&experience=&gender=&MExp=&genderB=&MPostings=&MCat=&version=&rpp={rpp}"
    "&Newspaper=&armyp=&QDisablePerson=&pwd=&workplace=&facilitiesForPWD=&SaveFilterList=&UserFilterName=&HUserFilterName="
    "&earlyJobAccess=&isPro=0&ToggleJobs=true&isFresher=false"
)

# 🔥 Job details API (your existing)
API_URL_TEMPLATE = "https://gateway.bdjobs.com/ActtivejobsTest/api/JobSubsystem/jobDetails?jobId={}"

REQUEST_DELAY = 0.3
LIST_API_DELAY = 0.2

MASTER_FILE = os.path.join(BASE_DIR, "Dataset/bdjobs_master_data.xlsx")
LOG_DIR = os.path.join(BASE_DIR, "logs")
SUMMARY_FILE = os.path.join(BASE_DIR, "run_summary.json")

# ================= LOGGING SETUP ================= #
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = datetime.now().strftime("bdjobs_run_%Y-%m-%d_%H-%M.log")
log_path = os.path.join(LOG_DIR, log_filename)

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)


# ================= HELPER FUNCTIONS ================= #
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


def extract_list_from_html(raw_html):
    if not raw_html:
        return []
    soup = BeautifulSoup(raw_html, "html.parser")
    items = [li.get_text(strip=True) for li in soup.find_all(["li", "p"])]
    return items if items else [soup.get_text(strip=True)]


def fetch_job_details_from_api(job_id):
    url = API_URL_TEMPLATE.format(job_id)
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if data.get("statuscode") != "0" or not data.get("data"):
            return None

        job = data["data"][0]
        return {
            "Job ID": str(job.get("JobId")),
            "Job Title": job.get("JobTitle"),
            "Company Name": job.get("CompnayName"),
            "Posted On": job.get("PostedOn"),
            "Deadline": job.get("Deadline"),
            "Vacancies": job.get("JobVacancies"),
            "Job Nature": job.get("JobNature"),
            "Workplace": job.get("JobWorkPlace"),
            "Education Requirements": extract_list_from_html(job.get("EducationRequirements")),
            "Experience": extract_list_from_html(job.get("experience")),
            "Additional Requirements": extract_list_from_html(job.get("AdditionJobRequirements")),
            "Skills Required": [s.strip() for s in (job.get("SkillsRequired") or "").split(",") if s.strip()],
            "Job Description": extract_list_from_html(job.get("JobDescription")),
            "Location": job.get("JobLocation"),
            "Salary Range": job.get("JobSalaryRange"),
            "Company Address": job.get("CompanyAddress"),
            "Apply Email": job.get("ApplyEmail"),
            "Apply Instruction": BeautifulSoup(job.get("ApplyInstruction") or "", "html.parser").get_text(strip=True),
            "Job Link": f"https://jobs.bdjobs.com/jobdetails.asp?id={job_id}"
        }

    except Exception as e:
        logging.error(f"❌ Error fetching job {job_id}: {e}")
        return None


def load_existing_job_ids():
    if not os.path.exists(MASTER_FILE):
        return set()
    try:
        df = pd.read_excel(MASTER_FILE, engine="openpyxl", dtype={'Job ID': str})
        if "Job ID" not in df.columns or df.empty:
            return set()
        id_series = (
            df["Job ID"]
            .dropna()
            .astype(str)
            .str.replace(r'\.0$', '', regex=True)
            .str.strip()
        )
        return set(id_series[id_series != ""].tolist())
    except Exception as e:
        logging.error(f"❌ Could not read master file: {e}")
        return set()


def save_to_master(new_data):
    df_new = pd.DataFrame(new_data)

    # Keep same columns formatting
    list_cols = ["Education Requirements", "Experience", "Additional Requirements", "Skills Required", "Job Description"]
    for col in list_cols:
        if col in df_new.columns:
            df_new[col] = df_new[col].apply(lambda x: "; ".join(x) if isinstance(x, list) else x)

    try:
        if os.path.exists(MASTER_FILE):
            df_old = pd.read_excel(MASTER_FILE, engine="openpyxl", dtype={'Job ID': str})
            df_combined = pd.concat([df_old, df_new], ignore_index=True)
            df_combined['Job ID'] = df_combined['Job ID'].astype(str)
            df_combined.drop_duplicates(subset=["Job ID"], keep="last", inplace=True)
        else:
            df_combined = df_new

        df_combined.to_excel(MASTER_FILE, index=False, engine="openpyxl")
        logging.info(f"✅ Merged into master. Total unique jobs: {len(df_combined)}")
        return len(df_combined)

    except Exception as e:
        logging.error(f"❌ Failed merging into master: {e}")
        backup_file = os.path.join(BASE_DIR, f"backup_bdjobs_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
        df_new.to_excel(backup_file, index=False)
        logging.warning(f"🆘 Saved new data separately as backup: {backup_file}")
        return -1


def fetch_job_ids_from_search_api(page_num: int, rpp: int):
    """
    Returns (job_ids_list, total_pages or None)
    Collects from both: data + premiumData
    """
    url = JOB_SEARCH_API_TEMPLATE.format(pg=page_num, rpp=rpp)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }

    resp = requests.get(url, headers=headers, timeout=25)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("statuscode") != "1":
        # API uses statuscode "1" for success in your example
        raise RuntimeError(f"JobSearch API not successful. statuscode={payload.get('statuscode')} message={payload.get('message')}")

    ids = []

    for item in (payload.get("data") or []):
        jid = item.get("Jobid") or item.get("JobId") or item.get("jobId")
        if jid:
            ids.append(str(jid))

    for item in (payload.get("premiumData") or []):
        jid = item.get("Jobid") or item.get("JobId") or item.get("jobId")
        if jid:
            ids.append(str(jid))

    total_pages = None
    common = payload.get("common") or {}
    if "totalpages" in common:
        try:
            total_pages = int(common["totalpages"])
        except Exception:
            total_pages = None

    return ids, total_pages


# ================= MAIN SCRAPER LOGIC ================= #
def main():
    logging.info("🚀 BDJobs Scraper started (API-based Job IDs)")

    existing_ids = load_existing_job_ids()
    existing_count = len(existing_ids)
    issues = []

    # 1) Discover total pages (optional, only if you want dynamic pages)
    total_pages = None
    try:
        first_ids, total_pages = fetch_job_ids_from_search_api(1, JOBS_PER_PAGE)
        all_job_ids = list(first_ids)
        logging.info(f"✅ Page 1 fetched. IDs: {len(first_ids)} | total_pages: {total_pages}")
    except Exception as e:
        logging.critical(f"💥 Failed to fetch JobSearch API page 1: {e}", exc_info=True)
        summary = {"status": "Crashed", "error": f"JobSearch API failed: {e}"}
        save_run_summary("BDJobs", summary)
        return

    # 2) Decide pages to scrape
    if PAGES_TO_SCRAPE is None and total_pages:
        pages_to_scrape = total_pages
    else:
        pages_to_scrape = PAGES_TO_SCRAPE

    # Safety: if API says fewer pages than configured
    if total_pages and pages_to_scrape and pages_to_scrape > total_pages:
        pages_to_scrape = total_pages

    # 3) Fetch remaining pages
    logging.info(f"--- Collecting Job IDs from {pages_to_scrape} pages via API ---")
    for page_num in tqdm(range(2, pages_to_scrape + 1), desc="Collecting BDJobs IDs (API)"):
        try:
            ids, _ = fetch_job_ids_from_search_api(page_num, JOBS_PER_PAGE)
            all_job_ids.extend(ids)
            time.sleep(LIST_API_DELAY)
        except Exception as e:
            logging.error(f"❌ JobSearch API error on page {page_num}: {e}")
            issues.append(f"Failed to collect IDs from API page {page_num}.")

    # 4) Deduplicate & filter new
    unique_job_ids = list(set(all_job_ids))
    new_job_ids = [jid for jid in unique_job_ids if jid not in existing_ids]

    logging.info(f"🧾 Total IDs collected (unique): {len(unique_job_ids)}")
    logging.info(f"🆕 New jobs to scrape: {len(new_job_ids)}")

    if not new_job_ids:
        summary = {
            "status": "No new jobs",
            "existing_jobs": existing_count,
            "newly_added": 0,
            "new_total": existing_count,
            "issues": issues
        }
        save_run_summary("BDJobs", summary)
        logging.info("✅ No new jobs found. Finished.")
        return

    # 5) Fetch details using your existing details API (keeps same columns)
    scraped_data, failed_job_scrapes = [], 0
    for job_id in tqdm(new_job_ids, desc="Scraping BDJobs Details"):
        job_details = fetch_job_details_from_api(job_id)
        if job_details:
            scraped_data.append(job_details)
        else:
            failed_job_scrapes += 1
        time.sleep(REQUEST_DELAY)

    if failed_job_scrapes > 0:
        issues.append(f"Failed to fetch details for {failed_job_scrapes} out of {len(new_job_ids)} new jobs.")

    # 6) Save
    newly_added_count, new_total_count = 0, existing_count
    status = "Completed"

    if scraped_data:
        new_total_count = save_to_master(scraped_data)
        if new_total_count != -1:
            newly_added_count = len(scraped_data)
            if issues:
                status = "Completed with issues"
        else:
            status = "Save Failed"
            issues.append("Critical error: Failed to save data to master file.")
            new_total_count = existing_count
    elif issues:
        status = "Failed"

    summary = {
        "status": status,
        "existing_jobs": existing_count,
        "newly_added": newly_added_count,
        "new_total": new_total_count,
        "issues": issues
    }
    save_run_summary("BDJobs", summary)
    logging.info("🏁 BDJobs Scraper finished.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"💥 BDJobs Global crash: {e}", exc_info=True)
        existing_count = len(load_existing_job_ids())
        summary = {
            "status": "Crashed",
            "existing_jobs": existing_count,
            "newly_added": 0,
            "new_total": existing_count,
            "issues": [f"Fatal script error: {e}"]
        }
        save_run_summary("BDJobs", summary)