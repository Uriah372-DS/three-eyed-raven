import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import numpy as np
from math import radians, cos, sin, asin, sqrt

# --- CONFIGURATION ---
st.set_page_config(page_title="The Corvid Shadow", layout="wide", page_icon="🦅")

# Default Constants (Pentagon & Perimeter)
lat = st.session_state.bases[st.session_state.target_base]['Latitude']
lon = st.session_state.bases[st.session_state.target_base]['Longitude']
DEFAULT_ZONE_A = f"{lat}, {lon}"
DEFAULT_ZONE_B = f"{lat}, {lon}"
TARGET_KEYWORDS = ["Crow", "Raven", "Corvus", "Jackal", "Jay", "Magpie"]

# --- MATH & LOGIC ---

def haversine(lon1, lat1, lon2, lat2):
    """Calculate distance (km) between two points."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    return c * 6371

@st.cache_data(ttl=3600)
def fetch_ebird_data(lat, lng, dist_km, api_key):
    """Fetches last 7 days of data in one call."""
    url = "https://api.ebird.org/v2/data/obs/geo/recent"
    headers = {'X-eBirdApiToken': api_key}
    params = {
        'lat': lat, 'lng': lng, 'dist': dist_km, 
        'back': 7, 'fmt': 'json'
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        return response.json() if response.status_code == 200 else []
    except:
        return []

def process_data(data_a, data_b, center_a, rad_a, rad_b, keywords):
    """
    1. Filter for Corvids.
    2. Remove Zone B birds that are actually inside Zone A.
    3. Return a cleaned DataFrame for analysis.
    """
    combined_rows = []
    
    # Process Zone A (The Base)
    for obs in data_a:
        name = obs.get('comName', '')
        if any(k.lower() in name.lower() for k in keywords):
            combined_rows.append({
                'Zone': 'Zone A (Base)',
                'Species': name,
                'Count': obs.get('howMany', 1) or 1,
                'Date': obs.get('obsDt', '')[:10], # Extract YYYY-MM-DD
                'lat': obs.get('lat'),
                'lng': obs.get('lng'),
                'loc': obs.get('locName')
            })

    # Process Zone B (The Suburb)
    for obs in data_b:
        name = obs.get('comName', '')
        if any(k.lower() in name.lower() for k in keywords):
            # GEOSPATIAL EXCLUSION CHECK
            dist_to_a = haversine(obs.get('lng'), obs.get('lat'), center_a['lng'], center_a['lat'])
            
            # Only count as 'Suburb' if it is physically OUTSIDE the Base radius
            if dist_to_a > rad_a:
                combined_rows.append({
                    'Zone': 'Zone B (Perimeter)',
                    'Species': name,
                    'Count': obs.get('howMany', 1) or 1,
                    'Date': obs.get('obsDt', '')[:10],
                    'lat': obs.get('lat'),
                    'lng': obs.get('lng'),
                    'loc': obs.get('locName')
                })
    
    return pd.DataFrame(combined_rows)

def calculate_time_series(df, rad_a, rad_b):
    """
    Groups data by date and calculates the Density Ratio for each day.
    """
    if df.empty: return pd.DataFrame()
    
    # 1. Calculate Areas
    area_a = np.pi * (rad_a**2)
    area_b = (np.pi * (rad_b**2)) - area_a # Donut Area
    
    # 2. Group by Date and Zone
    daily = df.groupby(['Date', 'Zone'])['Count'].sum().unstack(fill_value=0)
    
    # Ensure both columns exist
    if 'Zone A (Base)' not in daily.columns: daily['Zone A (Base)'] = 0
    if 'Zone B (Perimeter)' not in daily.columns: daily['Zone B (Perimeter)'] = 0
    
    # 3. Calculate Density (Count / Area)
    daily['Density_A'] = daily['Zone A (Base)'] / area_a
    daily['Density_B'] = daily['Zone B (Perimeter)'] / area_b
    
    # 4. Calculate Ratio (Density B / Density A)
    daily['Ratio'] = daily.apply(
        lambda row: row['Density_B'] / row['Density_A'] if row['Density_A'] > 0 else 0, axis=1
    )
    
    return daily

# --- UI LAYOUT ---

with st.sidebar:
    st.header("⚙️ Signal Configuration")
    
    # Use secrets if available, otherwise fallback to text input
    if 'EBIRD_API_KEY' in st.secrets:
        api_key = st.secrets['EBIRD_API_KEY']
    else:
        api_key = st.text_input("eBird API Key", type="password")
    
    st.subheader("Target Geofence")
    za_input = st.text_input("Target Coordinates (Lat, Lng)", value=DEFAULT_ZONE_A, help="The geographic center of the target facility.")
    za_rad = st.slider("Zone A Radius (Inner Circle)", 0.5, 5.0, 2.0, help="The 'Kill Zone' or immediate facility grounds.")
    zb_rad = st.slider("Zone B Radius (Outer Ring)", 2.0, 10.0, 5.0, help="The surrounding civilian buffer zone.")
    
    st.divider()
    
    if st.button("📡 Scan Frequencies"):
        st.cache_data.clear()
        st.rerun()

# Parse Coords
try:
    lat_a, lng_a = map(float, za_input.split(','))
    # Zone B uses same center (Concentric Bullseye)
    lat_b, lng_b = lat_a, lng_a 
except:
    st.error("Invalid Coordinates")
    st.stop()

# --- DATA PIPELINE ---

# 1. Fetch
raw_a = fetch_ebird_data(lat_a, lng_a, za_rad, api_key)
raw_b = fetch_ebird_data(lat_b, lng_b, zb_rad, api_key)

# 2. Process
df_clean = process_data(raw_a, raw_b, {'lat':lat_a, 'lng':lng_a}, za_rad, zb_rad, TARGET_KEYWORDS)

# 3. Analytics
if not df_clean.empty:
    daily_stats = calculate_time_series(df_clean, za_rad, zb_rad)
    
    # Current Metrics
    if not daily_stats.empty:
        latest_date = daily_stats.index.max()
        latest = daily_stats.loc[latest_date]
        current_ratio = latest['Ratio']
        
        # Volatility Calculation
        if len(daily_stats) > 1:
            mean_ratio = daily_stats['Ratio'].mean()
            std_ratio = daily_stats['Ratio'].std()
            z_score = (current_ratio - mean_ratio) / std_ratio if std_ratio > 0 else 0
        else:
            z_score = 0
            mean_ratio = current_ratio
    else:
        latest = {'Density_A': 0, 'Density_B': 0}
        current_ratio = 0
        z_score = 0
else:
    latest = {'Density_A': 0, 'Density_B': 0}
    current_ratio = 0
    z_score = 0

# --- DASHBOARD HEADER ---

st.title("👁️ The Corvid Shadow")

with st.expander("📖 Mission Briefing & Methodology", expanded=False):
    st.markdown("""
    **Objective:** Detect the displacement of hyper-intelligent crows from high-security zones (Zone A) to civilian suburbs (Zone B).
    
    **How to read this dashboard:**
    * **Zone A (Inner Circle):** The target facility. We measure bird density here.
    * **Zone B (Outer Ring):** The surrounding perimeter. We measure bird density here *excluding* the inner circle.
    * **Displacement Ratio:** If this number spikes, it means birds are fleeing the center and crowding the perimeter.
    * **Z-Score (Volatility):** Measures how weird today's movement is compared to the last 7 days. A score > 3.0 is a **confirmed anomaly**.
    """)

# --- ROW 1: METRICS ---

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Base Density (Zone A)", 
    f"{latest['Density_A']:.2f} /km²" if not df_clean.empty else "0", 
    help="Number of crows per square kilometer inside the facility."
)
col2.metric(
    "Perimeter Density (Zone B)", 
    f"{latest['Density_B']:.2f} /km²" if not df_clean.empty else "0", 
    help="Number of crows per square kilometer in the surrounding civilian buffer."
)
col3.metric(
    "Displacement Ratio", 
    f"{current_ratio:.2f}", 
    help="Formula: Perimeter Density / Base Density. \n\n• 1.0 = Balanced \n\n• >1.0 = Fleeing to Suburbs \n\n• <1.0 = Clustering at Base"
)
col4.metric(
    "Volatility Z-Score", 
    f"{z_score:.2f}", 
    delta="Alert Level", 
    delta_color="green" if z_score < 3.0 else "red",
    help="Statistical deviation from the 7-day average. \n\n• 0-2: Normal Noise \n\n• >3: Critical Anomaly (Something disturbed the flock)"
)

if z_score > 3.0:
    st.error("🚨 CRITICAL ANOMALY: Sudden, statistically significant shift in Corvid population detected.")

# --- ROW 2: VISUALS ---
st.divider()

c_map, c_chart = st.columns([1, 1])

with c_map:
    st.subheader("Geospatial SitRep")
    st.markdown("_Visual confirmation of flock distribution patterns._")
    
    m = folium.Map(location=[lat_a, lng_a], zoom_start=12)
    
    # Zones
    folium.Circle([lat_a, lng_a], radius=za_rad*1000, color="red", fill=True, fill_opacity=0.1, popup="Zone A (Base)").add_to(m)
    folium.Circle([lat_a, lng_a], radius=zb_rad*1000, color="blue", fill=True, fill_opacity=0.05, popup="Zone B (Perimeter)").add_to(m)
    
    # Points
    if not df_clean.empty:
        for _, row in df_clean.iterrows():
            color = "red" if "Zone A" in row['Zone'] else "blue"
            folium.CircleMarker(
                [row['lat'], row['lng']], radius=4, color=color, fill=True, 
                tooltip=f"{row['Species']} ({row['Count']})"
            ).add_to(m)
            
    st_folium(m, height=450, use_container_width=True)

with c_chart:
    st.subheader("Temporal Analysis (7-Day)")
    st.markdown("_Tracking the 'Flee Vector' over time. Spikes indicate sudden evacuations._")
    
    if not df_clean.empty:
        # Create a clean chart dataframe
        chart_df = daily_stats[['Ratio']].copy()
        chart_df.columns = ['Displacement Index']
        
        st.line_chart(chart_df)
        
        # Additional context below chart
        avg_val = daily_stats['Ratio'].mean()
        st.caption(f"Average Baseline: {avg_val:.2f}. Deviations above this line suggest unusual perimeter activity.")
    else:
        st.warning("No data available for charts.")

# --- ROW 3: RAW INTEL ---
st.divider()
with st.expander("📂 View Raw Intelligence Log"):
    st.markdown("Full manifest of intercepted avian signals.")
    if not df_clean.empty:
        st.dataframe(
            df_clean[['Date', 'Zone', 'Species', 'Count', 'loc']].sort_values(['Date', 'Zone'], ascending=False),
            width='stretch'
        )