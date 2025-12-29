# FILE: api.py (NEW)

from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import psycopg2

app = Flask(__name__)
CORS(app)

# Credentials will be loaded from the Render environment
DB_HOST = os.environ.get("DB_HOST")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_USER = "postgres"
DB_NAME = "postgres"

def get_db_connection():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)

# Endpoint 1: High-level KPIs
@app.route('/api/kpi')
def get_kpi():
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
    SELECT
        COUNT(*),
        COUNT(DISTINCT company_name),
        COUNT(DISTINCT country)
    FROM jobs;
    """
    cur.execute(query)
    total_jobs, total_companies, total_countries = cur.fetchone()
    cur.close()
    conn.close()
    return jsonify({
        "total_jobs": total_jobs,
        "total_companies": total_companies,
        "total_countries": total_countries
    })

# Endpoint 2: Flexible distributions (Top N for a given variable and country)
@app.route('/api/distribution')
def get_distribution():
    country = request.args.get('country', 'All')
    variable = request.args.get('variable', 'company_name') # e.g., company_name, location, skills
    
    if variable not in ['company_name', 'location', 'skills']:
        return jsonify({"error": "Invalid variable"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    
    # Base query
    query = f"SELECT {variable}, COUNT(*) as count FROM jobs"
    
    # Add country filter if specified
    params = ()
    if country != 'All':
        query += " WHERE country = %s"
        params = (country,)
    
    # Complete the query
    query += f" AND {variable} IS NOT NULL AND {variable} != '' GROUP BY {variable} ORDER BY count DESC LIMIT 15;"
    
    cur.execute(query, params)
    data = [{"name": row[0], "count": row[1]} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(data)

# Endpoint 3: Trend Analysis (Job postings over time)
@app.route('/api/trend')
def get_trend():
    country = request.args.get('country', 'All')
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
    SELECT DATE_TRUNC('month', posted_on)::date as month, COUNT(*) as count
    FROM jobs
    WHERE posted_on IS NOT NULL
    """
    params = ()
    if country != 'All':
        query += " AND country = %s"
        params = (country,)
        
    query += " GROUP BY month ORDER BY month;"
    
    cur.execute(query, params)
    data = [{"month": row[0].strftime('%Y-%m'), "count": row[1]} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(data)

# Endpoint 4: Regional Comparison
@app.route('/api/region-comparison')
def get_region_comparison():
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
    SELECT region, COUNT(*) as count
    FROM jobs
    WHERE region IS NOT NULL
    GROUP BY region
    ORDER BY count DESC;
    """
    cur.execute(query)
    data = [{"region": row[0], "count": row[1]} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))