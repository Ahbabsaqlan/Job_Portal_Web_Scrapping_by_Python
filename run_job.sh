#!/bin/bash

# ================= CONFIGURATION ================= #
BASE_DIR="/Users/jihan/JobWebScrapper"
PYTHON_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"

# --- Script file paths ---
BDJOBS_SCRIPT="$BASE_DIR/Bangladesh/BDjobsMaster.py"
JOBSTREET_SG_SCRIPT="$BASE_DIR/Singapore/jobstreet_SG.py" 
#JOBSTREET_MY_SCRIPT="$BASE_DIR/Malaysia/JobStreet_MY.py"
JOBSTREET_PH_SCRIPT="$BASE_DIR/Phillipine/JobStreet_PH.py"
JOBSTREET_ID_SCRIPT="$BASE_DIR/Indonesia/jobstreet_ID.py"
NOUKRI_SCRIPT="$BASE_DIR/Indian/Noukri.py"
ROZEE_SCRIPT="$BASE_DIR/Pakistani/rozee.py"
EMAIL_SCRIPT="$BASE_DIR/send_summary_email.py"

RUN_LOG="$BASE_DIR/launchd_run.log"

# ================= START LOG ================= #
echo "======================================================================" >> "$RUN_LOG"
echo "[$(date)] 🚀 Starting Scraper Sequence..." >> "$RUN_LOG"
echo "======================================================================" >> "$RUN_LOG"

echo "[$(date)] --- Cleaning up old summary file... ---" >> "$RUN_LOG"
rm -f "$BASE_DIR/run_summary.json"

# ================= KEEP MAC AWAKE ================= #
caffeinate -dimsu &  
CAFFEINATE_PID=$!

# ================= RUN SCRAPERS ================= #

# --- PART 1: BDJOBS ---
echo "[$(date)] --- Starting BDJobs Scraper ---" >> "$RUN_LOG"
"$PYTHON_BIN" "$BDJOBS_SCRIPT" >> "$RUN_LOG" 2>&1
echo "[$(date)] ✅ BDJobs scraper finished." >> "$RUN_LOG"

# --- PART 2: NAUKRI ---
echo "" >> "$RUN_LOG"
echo "[$(date)] --- Starting Naukri.com Scraper ---" >> "$RUN_LOG"
"$PYTHON_BIN" "$NOUKRI_SCRIPT" >> "$RUN_LOG" 2>&1
echo "[$(date)] ✅ Naukri.com scraper finished." >> "$RUN_LOG"

# --- PART 3: ROZEE.PK ---
echo "" >> "$RUN_LOG"
echo "[$(date)] --- Starting Rozee.pk Scraper ---" >> "$RUN_LOG"
"$PYTHON_BIN" "$ROZEE_SCRIPT" >> "$RUN_LOG" 2>&1
echo "[$(date)] ✅ Rozee.pk scraper finished." >> "$RUN_LOG"

# --- PART 4: JOBSTREET (ALL COUNTRIES) ---
echo "" >> "$RUN_LOG"
echo "[$(date)] --- Starting JobStreet (SG) Scraper ---" >> "$RUN_LOG"
"$PYTHON_BIN" "$JOBSTREET_SG_SCRIPT" >> "$RUN_LOG" 2>&1

# echo "" >> "$RUN_LOG"
# echo "[$(date)] --- Starting JobStreet (MY) Scraper ---" >> "$RUN_LOG"
# "$PYTHON_BIN" "$JOBSTREET_MY_SCRIPT" >> "$RUN_LOG" 2>&1

echo "" >> "$RUN_LOG"
echo "[$(date)] --- Starting JobStreet (PH) Scraper ---" >> "$RUN_LOG"
"$PYTHON_BIN" "$JOBSTREET_PH_SCRIPT" >> "$RUN_LOG" 2>&1

echo "" >> "$RUN_LOG"
echo "[$(date)] --- Starting JobStreet (ID) Scraper ---" >> "$RUN_LOG"
"$PYTHON_BIN" "$JOBSTREET_ID_SCRIPT" >> "$RUN_LOG" 2>&1

echo "[$(date)] ✅ JobStreet scrapers finished." >> "$RUN_LOG"

# ================= SEND FINAL SUMMARY EMAIL ================= #
echo "" >> "$RUN_LOG"
echo "[$(date)] --- Running Final Summary Email Script ---" >> "$RUN_LOG"
"$PYTHON_BIN" "$EMAIL_SCRIPT" >> "$RUN_LOG" 2>&1

# ================= CLEANUP & FINAL LOG ================= #
kill $CAFFEINATE_PID
echo "" >> "$RUN_LOG"
echo "[$(date)] 🏁 Scraper Sequence Finished." >> "$RUN_LOG"
echo "" >> "$RUN_LOG"