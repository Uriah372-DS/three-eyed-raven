import streamlit as st
import nexradaws
import pyart
import pandas as pd
import numpy as np
import plotly.express as px
import datetime
import os
import shutil

# --- UI CONFIGURATION ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 10px; }
    .stAlert { background-color: #1a1c23; border: 1px solid #00FF41; }
    </style>
""", unsafe_allow_html=True)

# --- CORE LOGIC ---
def fetch_and_process(radar_id):
    conn = nexradaws.NexradAwsInterface()
    now = datetime.datetime.utcnow()
    
    try:
        scans = conn.get_avail_scans(now.year, now.month, now.day, radar_id)
        if not scans:
            return None, "No scans found for today."
        
        data_scans = [s for s in scans if not s.filename.endswith('_MDM')]
        if not data_scans:
            return None, "Radar in maintenance or only metadata available."

        temp_dir = 'temp_nexrad'
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            
        results = conn.download(data_scans[-1], temp_dir)
        if len(results.success) == 0:
            return None, "Download failed."
            
        local_file = results.success[0].filepath
        
        try:
            radar = pyart.io.read(local_file)
        except Exception as read_err:
            return None, f"Py-ART Read Error: {read_err}"
        
        shutil.rmtree(temp_dir)
        return radar, None
    except Exception as e:
        return None, f"Connection Error: {str(e)}"

def extract_tactical_data(radar):
    try:
        sweep = 0
        if 'reflectivity' not in radar.fields or 'cross_correlation_ratio' not in radar.fields:
            return pd.DataFrame()

        start, end = radar.get_start(sweep), radar.get_end(sweep)
        
        ref = radar.fields['reflectivity']['data'][start:end]
        rho = radar.fields['cross_correlation_ratio']['data'][start:end]
        
        gate_lat = radar.gate_latitude['data'][start:end].flatten()
        gate_lon = radar.gate_longitude['data'][start:end].flatten()
        
        df = pd.DataFrame({
            'lat': gate_lat,
            'lon': gate_lon,
            'Reflectivity_dBZ': ref.flatten(),
            'Static_Index_RhoHV': rho.flatten()
        }).dropna()
        
        # Filter for Biological range (5-30 dBZ)
        # This is the "Bird Filter" - rain is usually > 30 dBZ
        df = df[(df['Reflectivity_dBZ'] >= 5) & (df['Reflectivity_dBZ'] <= 30)]
        
        if len(df) > 12000:
            df = df.sample(n=12000)
            
        return df
    except:
        return pd.DataFrame()

# --- DASHBOARD UI ---
st.title("🧲 The Magnetic Static")
st.caption(f"Module: EYE 02 - Avian Radar Distress ({st.session_state.target_base} Sector)")

# Mission Briefing Expander
with st.expander("📖 Mission Briefing & Avian Logic", expanded=True):
    st.markdown("""
    **The Objective:** Use birds as biological sensors for Electronic Warfare (EW). 
    
    **The Logic:** 
                
    1. **Avian Sensitivity:** Many birds use **magnetoreception** (a biological compass) to navigate. 

    2. **The Pulse:** When a military facility activates high-powered radar or GPS jammers, it creates a "Magnetic Static" that disorients the local avian population.
    
    3. **Radar Detection:** We use NEXRAD radar to find **Biological Targets** ($5-30$ dBZ). We then measure their **Correlation Coefficient ($\\rho_{hv}$)**. 
    
    **The Signal:** In normal flight, birds have a high $\\rho_{hv}$. If $\\rho_{hv}$ drops significantly while biomass is present, it indicates the birds are flying erratically or the radar signal is being jammed—both are **strong indicators of active EW suites.**
    """)



# Get current radar from session state
radar_id = st.session_state.get('active_radar', 'KLWX')

with st.sidebar:
    st.header("Tactical Focus")
    st.write(f"**Target:** {st.session_state.target_base}")
    st.write(f"**Bio-Radar Node:** {radar_id}")
    st.write(f"**Sector:** {st.session_state.active_lat}, {st.session_state.active_lon}")
    st.divider()
    st.info("""
    **Avian Legend:**
    * **High Integrity ($>0.95$):** Stable bird flight/migration.
    * **Low Integrity ($<0.90$):** Disoriented flocking or Electronic Interference.
    """)

# Automated Load Sequence
with st.spinner(f"Interrogating {radar_id} Bio-Acoustic uplink..."):
    radar, error = fetch_and_process(radar_id)

if error:
    st.error(f"Intercept Failed: {error}")
else:
    df = extract_tactical_data(radar)
    
    if df.empty:
        st.warning("Atmosphere clear: No avian biomass detected in sector.")
    else:
        avg_static = df['Static_Index_RhoHV'].mean()
        
        # KPI Row with Tooltips
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(
                "Detected Avian Biomass", 
                f"{len(df)} units", 
                help="The estimated number of biological pings (birds/insects) in the air. Filtered for 5-30 dBZ to exclude weather."
            )
        with c2:
            status = "STABLE" if avg_static > 0.93 else "FLOCK DISTRESS"
            st.metric(
                "Avian Flight Integrity", 
                status, 
                delta=f"{avg_static:.3f} ρhv",
                help="Correlation coefficient (RhoHV). A drop in this value among birds often indicates disorientation caused by high-power electronic emissions."
            )
        with c3:
            st.metric(
                "Sensor Node", 
                radar_id, 
                "Active",
                help="The active NEXRAD station monitoring this base's airspace."
            )

        # Map Visualization
        st.subheader(f"Avian Signal Map: {st.session_state.target_base} Sector")
        
        fig = px.scatter_mapbox(
            df, 
            lat="lat", 
            lon="lon", 
            color="Static_Index_RhoHV",
            size="Reflectivity_dBZ",
            color_continuous_scale="Viridis",
            range_color=[0.7, 1.0],
            mapbox_style="open-street-map",
            center={"lat": st.session_state.active_lat, "lon": st.session_state.active_lon},
            zoom=8,
            height=650,
            hover_data={
                "lat": False, 
                "lon": False, 
                "Static_Index_RhoHV": ":.4f", 
                "Reflectivity_dBZ": ":.1f"
            },
            labels={"Static_Index_RhoHV": "Flight Integrity", "Reflectivity_dBZ": "Bird Density"}
        )
        
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig, width='stretch')
        
        with st.expander("📂 View Raw Avian Intelligence Log"):
            st.dataframe(df.head(100), width='stretch')