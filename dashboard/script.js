// FILE: dashboard/script.js

// IMPORTANT: Replace this with your live Render API URL after deployment
const API_BASE_URL = 'https://your-api-name.onrender.com';

// Chart instances need to be stored globally to be destroyed and re-created
let trendChart, companyChart, locationChart, regionChart;

// --- Chart Rendering Helper ---
function renderChart(canvasId, chartInstance, type, labels, data, chartLabel) {
    if (chartInstance) {
        chartInstance.destroy(); // Destroy previous chart instance if it exists
    }
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: type,
        data: {
            labels: labels,
            datasets: [{ label: chartLabel, data: data, borderWidth: 1, backgroundColor: type === 'line' ? 'rgba(75, 192, 192, 0.2)' : 'rgba(75, 192, 192, 0.6)', borderColor: 'rgba(75, 192, 192, 1)' }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: type.includes('bar') || type.includes('line') ? { y: { beginAtZero: true } } : {}
        }
    });
}

// --- Data Fetching Functions ---
async function fetchKPIs() {
    const response = await fetch(`${API_BASE_URL}/api/kpi`);
    const data = await response.json();
    document.getElementById('kpi-total-jobs').textContent = data.total_jobs.toLocaleString();
    document.getElementById('kpi-total-companies').textContent = data.total_companies.toLocaleString();
    document.getElementById('kpi-total-countries').textContent = data.total_countries.toLocaleString();
}

async function fetchRegionData() {
    const response = await fetch(`${API_BASE_URL}/api/region-comparison`);
    const data = await response.json();
    const labels = data.map(d => d.region);
    const values = data.map(d => d.count);
    regionChart = renderChart('regionChart', regionChart, 'pie', labels, values, 'Jobs by Region');
}

async function updateDashboard(country = 'All') {
    console.log(`Updating dashboard for: ${country}`);
    
    // Fetch and render trend chart
    const trendRes = await fetch(`${API_BASE_URL}/api/trend?country=${country}`);
    const trendData = await trendRes.json();
    trendChart = renderChart('trendChart', trendChart, 'line', trendData.map(d => d.month), trendData.map(d => d.count), 'Job Postings');

    // Fetch and render top companies chart
    const companyRes = await fetch(`${API_BASE_URL}/api/distribution?variable=company_name&country=${country}`);
    const companyData = await companyRes.json();
    companyChart = renderChart('companyChart', companyChart, 'bar', companyData.map(d => d.name), companyData.map(d => d.count), 'Top Companies');

    // Fetch and render top locations chart
    const locationRes = await fetch(`${API_BASE_URL}/api/distribution?variable=location&country=${country}`);
    const locationData = await locationRes.json();
    locationChart = renderChart('locationChart', locationChart, 'bar', locationData.map(d => d.name), locationData.map(d => d.count), 'Top Locations');
}

// --- Initial Load and Event Listeners ---
document.addEventListener('DOMContentLoaded', () => {
    // Initial data load
    fetchKPIs();
    fetchRegionData(); // This one doesn't depend on the country filter
    updateDashboard(); // Load with "All" countries initially

    // Add event listener for the dropdown
    document.getElementById('country-select').addEventListener('change', (event) => {
        updateDashboard(event.target.value);
    });
});