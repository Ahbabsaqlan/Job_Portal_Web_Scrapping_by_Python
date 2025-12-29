# FILE: db_handler.py
import os
from supabase import create_client, Client

# These credentials will be loaded from the cloud environment
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_jobs_to_db(jobs_list):
    """
    Saves a list of job dictionaries to the Supabase 'jobs' table.
    Uses 'upsert' to insert new jobs or update existing ones based on job_url.
    """
    if not supabase or not jobs_list:
        print("Database client not initialized or job list is empty.")
        return 0
    try:
        # on_conflict='job_url' tells Supabase to use this column as the unique key
        data, count = supabase.table('jobs').upsert(jobs_list, on_conflict='job_url').execute()
        num_affected = len(data[1]) if data and len(data) > 1 else 0
        print(f"✅ Successfully upserted {num_affected} jobs.")
        return num_affected
    except Exception as e:
        print(f"❌ Database Error: {e}")
        return 0