#!/usr/bin/env python3
import os
import smtplib
import json
import logging
import io
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()


# Email & MIME
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

# Visualization
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

# ================= CONFIGURATION ================= #
BASE_DIR = "/Users/jihan/JobData"
SUMMARY_FILE = os.path.join(BASE_DIR, "run_summary.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# --- Email Config ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = "ahbabzami3@gmail.com"
EMAIL_PASSWORD = os.getenv("EMAIL_PASS") # App Password
EMAIL_RECEIVERS = [
    "22-48108-2@student.aiub.edu",
    "22-48091-2@student.aiub.edu"
]

# ================= LOGGING ================= #
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = datetime.now().strftime("email_summary_run_%Y-%m-%d_%H-%M.log")
logging.basicConfig(filename=os.path.join(LOG_DIR, log_filename), level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

# ================= 1. VISUALIZATION ENGINE ================= #

def generate_charts(df):
    images = {}
    sns.set_theme(style="white") 

    # --- CHART A: NEW JOBS (Horizontal Bar) ---
    new_jobs_df = df[df['Newly Added'] > 0].sort_values('Newly Added', ascending=False)
    
    if not new_jobs_df.empty:
        plt.figure(figsize=(8, 4))
        
        # FIX 1: Added hue="Source" and legend=False to silence warning
        ax = sns.barplot(x="Newly Added", y="Source", data=new_jobs_df, palette="viridis", hue="Source", legend=False)
        
        # FIX 2: Removed Emoji from chart title to fix Glyph warning
        plt.title("Performance: Newly Added Jobs Today", fontsize=12, fontweight='bold', pad=15)
        plt.xlabel("Number of Jobs Added")
        plt.ylabel("")
        sns.despine(left=True, bottom=True)
        
        # Add values to bars
        for i, v in enumerate(new_jobs_df['Newly Added']):
            ax.text(v + (v * 0.01), i, f" +{v:,}", color='black', va='center', fontweight='bold')

        plt.tight_layout()
        
        buf_bar = io.BytesIO()
        plt.savefig(buf_bar, format='png', dpi=100, bbox_inches='tight')
        buf_bar.seek(0)
        images['bar_chart'] = buf_bar.getvalue()
        plt.close()

    # --- CHART B: TOTAL DISTRIBUTION (Donut Chart) ---
    active_df = df[df['Total Jobs'] > 0]
    
    if not active_df.empty:
        plt.figure(figsize=(6, 6))
        colors = sns.color_palette('pastel')[0:len(active_df)]
        plt.pie(active_df['Total Jobs'], labels=active_df['Source'], colors=colors, 
                autopct='%1.1f%%', startangle=90, pctdistance=0.85, wedgeprops=dict(width=0.4))
        
        # FIX 2: Removed Emoji
        plt.title("Total Database Distribution", fontsize=12, fontweight='bold')
        
        buf_pie = io.BytesIO()
        plt.savefig(buf_pie, format='png', dpi=100, bbox_inches='tight')
        buf_pie.seek(0)
        images['pie_chart'] = buf_pie.getvalue()
        plt.close()
    
    return images

# ================= 2. RESPONSIVE HTML GENERATOR ================= #

def generate_responsive_html(df, grand_totals, issue_list):
    
    # Table Rows Generation
    table_rows = ""
    for _, row in df.iterrows():
        if "fail" in str(row['Status']).lower() or "crash" in str(row['Status']).lower():
            badge_style = "background-color: #ffebee; color: #c62828; border: 1px solid #ffcdd2;"
        elif row['Newly Added'] > 0:
            badge_style = "background-color: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9;"
        else:
            badge_style = "background-color: #f5f5f5; color: #616161; border: 1px solid #e0e0e0;"

        new_jobs_display = f"+{row['Newly Added']:,}" if row['Newly Added'] > 0 else "-"
        new_jobs_style = "color: #2e7d32; font-weight: bold;" if row['Newly Added'] > 0 else "color: #ccc;"

        table_rows += f"""
        <tr>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee;">
                <div style="font-weight: bold; color: #333;">{row['Source']}</div>
                <div style="font-size: 11px; margin-top: 4px;">
                    <span style="padding: 2px 6px; border-radius: 4px; font-size: 10px; {badge_style}">{row['Status']}</span>
                </div>
            </td>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee; text-align: right; {new_jobs_style}">{new_jobs_display}</td>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee; text-align: right; color: #555;">{row['Total Jobs']:,}</td>
        </tr>
        """

    issue_section = ""
    if issue_list:
        items = "".join([f"<li style='margin-bottom: 5px;'>{i}</li>" for i in issue_list])
        issue_section = f"""
        <div style="background-color: #fff3e0; border-left: 4px solid #ff9800; padding: 15px; margin-bottom: 20px; border-radius: 4px;">
            <h4 style="margin: 0 0 10px 0; color: #ef6c00;">⚠️ Attention Required</h4>
            <ul style="margin: 0; padding-left: 20px; color: #5d4037; font-size: 13px;">{items}</ul>
        </div>
        """

    # --- HTML & CSS FIXES ---
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style type="text/css">
            /* Base */
            body {{ margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f4f4; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; }}
            
            /* Responsive Logic */
            /* We use a class for the column */
            .three-col {{
                display: inline-block;
                width: 32%;
                min-width: 150px;
                vertical-align: top;
                box-sizing: border-box;
            }}

            /* MOBILE OVERRIDE */
            @media only screen and (max-width: 480px) {{
                .container {{ width: 100% !important; }}
                .three-col {{ 
                    width: 100% !important; 
                    display: block !important; 
                    margin-bottom: 15px !important; 
                }}
                h1 {{ font-size: 20px !important; }}
            }}
        </style>
    </head>
    <body>
        <div class="container" style="border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-top: 20px; margin-bottom: 20px; overflow: hidden;">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%); padding: 25px; text-align: center; color: white;">
                <h1 style="margin: 0; font-size: 24px;">📊 Scraper Daily Report</h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 14px;">{datetime.now().strftime('%A, %d %B %Y')}</p>
            </div>

            <div style="padding: 15px;">
                {issue_section}

                <!-- STATS CARDS (Responsive) -->
                <!-- We use font-size: 0 to remove whitespace between inline-blocks -->
                <div style="text-align: center; font-size: 0; padding: 10px 0;">
                    
                    <!-- Card 1 -->
                    <div class="three-col" style="padding: 5px;">
                        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-bottom: 3px solid #3498db; border: 1px solid #eee;">
                            <div style="font-size: 11px; text-transform: uppercase; color: #7f8c8d; letter-spacing: 1px; font-family: sans-serif;">Previous Total</div>
                            <div style="font-size: 20px; font-weight: 800; color: #2c3e50; margin-top: 5px; font-family: sans-serif;">{grand_totals['existing']:,}</div>
                        </div>
                    </div>

                    <!-- Card 2 -->
                    <div class="three-col" style="padding: 5px;">
                        <div style="background-color: #f1f8e9; padding: 15px; border-radius: 8px; border-bottom: 3px solid #2ecc71; border: 1px solid #c8e6c9;">
                            <div style="font-size: 11px; text-transform: uppercase; color: #2e7d32; letter-spacing: 1px; font-family: sans-serif;">Added Today</div>
                            <div style="font-size: 20px; font-weight: 800; color: #2e7d32; margin-top: 5px; font-family: sans-serif;">+{grand_totals['added']:,}</div>
                        </div>
                    </div>

                    <!-- Card 3 -->
                    <div class="three-col" style="padding: 5px;">
                        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-bottom: 3px solid #9b59b6; border: 1px solid #eee;">
                            <div style="font-size: 11px; text-transform: uppercase; color: #7f8c8d; letter-spacing: 1px; font-family: sans-serif;">New Grand Total</div>
                            <div style="font-size: 20px; font-weight: 800; color: #2c3e50; margin-top: 5px; font-family: sans-serif;">{grand_totals['total']:,}</div>
                        </div>
                    </div>

                </div>
                <!-- End Stats Cards -->

                <!-- Visuals Section -->
                <div style="padding: 10px; text-align: center; margin-top: 10px;">
                    <h3 style="color: #333; font-size: 16px; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 10px; font-family: sans-serif;">📉 Data Insights</h3>
                    
                    {'<img src="cid:bar_chart" style="max-width: 100%; height: auto; border-radius: 6px; margin-bottom: 20px;">' if grand_totals['added'] > 0 else '<p style="color:#999; font-style:italic;">No new jobs added today.</p>'}
                    
                    <img src="cid:pie_chart" style="max-width: 80%; height: auto; border-radius: 6px;">
                </div>

                <!-- Data Table -->
                <div style="padding: 10px;">
                    <h3 style="color: #333; font-size: 16px; margin-bottom: 10px; font-family: sans-serif;">📋 Source Breakdown</h3>
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                        <thead>
                            <tr style="background-color: #f8f9fa; text-align: left;">
                                <th style="padding: 10px; border-bottom: 2px solid #ddd; color: #777; font-weight: 600;">Source</th>
                                <th style="padding: 10px; border-bottom: 2px solid #ddd; color: #777; font-weight: 600; text-align: right;">Added</th>
                                <th style="padding: 10px; border-bottom: 2px solid #ddd; color: #777; font-weight: 600; text-align: right;">Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>

                <!-- Footer -->
                <div style="text-align: center; padding: 20px; color: #999; font-size: 12px; border-top: 1px solid #eee; margin-top: 20px; font-family: sans-serif;">
                    Automated by Job Data Pipeline<br>
                    Run ID: {datetime.now().strftime('%Y%m%d-%H%M')}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html

# ================= 3. SENDING LOGIC ================= #

def send_email(subject, html_body, images):
    try:
        msg = MIMEMultipart('related')
        msg["From"] = f"Job Scrapper 🤖"
        msg["To"] = ", ".join(EMAIL_RECEIVERS)
        msg["Subject"] = subject

        # Attach HTML
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Attach Images
        for img_id, img_data in images.items():
            if img_data:
                img = MIMEImage(img_data)
                img.add_header('Content-ID', f'<{img_id}>')
                img.add_header('Content-Disposition', 'inline')
                msg.attach(img)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVERS, msg.as_string())
        
        logging.info("✅ Email sent successfully.")

    except Exception as e:
        logging.error(f"❌ Failed to send email: {e}")

# ================= MAIN ================= #

def main():
    logging.info("🚀 Building summary...")
    
    if not os.path.exists(SUMMARY_FILE):
        logging.error("Summary file missing.")
        return

    try:
        with open(SUMMARY_FILE, 'r') as f:
            summaries = json.load(f)
    except:
        return

    scraper_order = ["BDJobs", "Noukri.com", "Rozee.pk", "JobStreet (SG)", "JobStreet (PH)", "JobStreet (ID)"]
    data_list = []
    all_issues = []
    grand_totals = {'existing': 0, 'added': 0, 'total': 0}

    for name in scraper_order:
        stats = summaries.get(name, {})
        
        existing = int(stats.get('existing_jobs', 0) or 0)
        added = int(stats.get('newly_added', 0) or 0)
        total = int(stats.get('new_total', 0) or 0)
        status = stats.get('status', 'Skipped')
        
        if stats.get('issues'):
            for i in stats['issues']: all_issues.append(f"<b>{name}:</b> {i}")

        grand_totals['existing'] += existing
        grand_totals['added'] += added
        grand_totals['total'] += total

        data_list.append({
            "Source": name, "Status": status,
            "Existing Jobs": existing, "Newly Added": added, "Total Jobs": total
        })

    df = pd.DataFrame(data_list)
    images = generate_charts(df)
    html_body = generate_responsive_html(df, grand_totals, all_issues)
    
    icon = "🚀" if grand_totals['added'] > 0 else "💤"
    if all_issues: icon = "⚠️"
    
    subject = f"{icon} Scraper Report: +{grand_totals['added']} Jobs Added"
    send_email(subject, html_body, images)
    
    try: os.remove(SUMMARY_FILE)
    except: pass

if __name__ == "__main__":
    main()