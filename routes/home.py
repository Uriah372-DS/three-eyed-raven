import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from utils.raven_logic import fetch_infrasound_intel, fetch_magnetic_intel, fetch_corvid_intel

# --- UI STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    h1, h2, h3 { color: #00FF41 !important; font-family: 'Courier New', monospace; }
    .stMetric { border: 1px solid #333; padding: 10px; border-radius: 5px; background: #1a1c23; }
    .indicator-box { 
        padding: 20px; 
        border-radius: 10px; 
        text-align: center; 
        border: 2px solid #00FF41;
        background-color: #161b22;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🐦‍⬛ THE THREE-EYED RAVEN")
st.write(f"### *Strategic Intelligence Hub: {st.session_state.target_base}*")

# --- DATA ACQUISITION ---
api_key = st.secrets.get("EBIRD_API_KEY", "")
with st.status(f"Interrogating Sector {st.session_state.target_base}...", expanded=False) as status:
    infra = fetch_infrasound_intel(st.session_state.active_lat, st.session_state.active_lon)
    mag = fetch_magnetic_intel(st.session_state.active_radar)
    corvid = fetch_corvid_intel(st.session_state.active_lat, st.session_state.active_lon, api_key)
    status.update(label="Sector Scan Complete", state="complete")

# --- UNIFIED INDICATOR CALCULATION (RPI) ---
# We normalize each KPI to a 0.0 - 1.0 scale of "Anomaly"
infra_score = min(abs(infra['delta']) / 60, 1.0) # Threshold at 60% delta
mag_score = min(max(0, (0.98 - mag['avg_rho']) / 0.08), 1.0) # 0.98 (Nominal) to 0.90 (Critical)
corvid_score = min(max(0, (corvid['ratio'] - 1.0) / 2.0), 1.0) # 1.0 (Balanced) to 3.0 (Displaced)

# Weighted Average: We weight Magnetic and Infrasound higher as they are leading indicators
rpi_raw = (infra_score * 0.35) + (mag_score * 0.40) + (corvid_score * 0.25)
rpi_percent = round(rpi_raw * 100, 1)

# Determine Color and Label
if rpi_percent < 30:
    rpi_color, rpi_label = "#00FF41", "STABLE"
elif rpi_percent < 70:
    rpi_color, rpi_label = "#FFA500", "ELEVATED ANOMALY"
else:
    rpi_color, rpi_label = "#FF4B4B", "CRITICAL DISRUPTION"

# --- RADAR CHART DATA ---
categories = ['Acoustic (Infra)', 'Electronic (Mag)', 'Social (Corvid)']
current_vals = [infra_score * 100, mag_score * 100, corvid_score * 100]
thresholds = [40, 50, 50]

fig = go.Figure()
fig.add_trace(go.Scatterpolar(r=thresholds, theta=categories, fill='toself', name='Baseline', line_color='rgba(255, 75, 75, 0.3)'))
fig.add_trace(go.Scatterpolar(r=current_vals, theta=categories, fill='toself', name='Current Signal', line_color='#00FF41'))
fig.update_layout(
    polar=dict(radialaxis=dict(visible=False, range=[0, 100]), bgcolor="#1a1c23"),
    showlegend=False, paper_bgcolor="#0e1117", font_color="#00FF41", height=400,
    margin=dict(l=50, r=50, t=20, b=20)
)

# --- LAYOUT ---
st.divider()
m1, m2, m3 = st.columns(3)
m1.metric("Acoustic Delta", f"{infra['delta']}%", delta="Spike" if abs(infra['delta']) > 40 else None)
m2.metric("Signal Integrity", f"{mag['avg_rho']} ρhv", delta="-EMI" if mag['avg_rho'] < 0.94 else None, delta_color="inverse")
m3.metric("Avian Displacement", f"{corvid['ratio']}x", delta="EVAC" if corvid['ratio'] > 2.5 else None, delta_color="inverse")

st.divider()
left, right = st.columns([1, 1])

with left:
    # THE UNIFIED INDICATOR DISPLAY
    st.markdown(f"""
        <div class="indicator-box" style="border-color: {rpi_color};">
            <p style="color: #fafafa; margin-bottom: 5px; font-size: 14px;">RAVEN PROBABILITY INDEX (RPI)</p>
            <h1 style="color: {rpi_color} !important; font-size: 48px; margin: 0;">{rpi_percent}%</h1>
            <p style="color: {rpi_color}; font-weight: bold; margin-top: 5px;">STATUS: {rpi_label}</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🕸️ Multi-Vector Threat Map")
    st.plotly_chart(fig, width='stretch')

with right:
    st.markdown("### 👁️ Intelligence Synopsis")
    if rpi_percent >= 70:
        st.error(f"🚨 **CRITICAL CORRELATION**: Environmental vectors at {st.session_state.target_base} have decoupled from biological baselines. High confidence of strategic activity.")
    elif rpi_percent >= 30:
        st.warning("⚠️ **WEAK SIGNAL**: Significant atmospheric or biological variance detected. Monitoring sub-audible frequencies for confirmation.")
    else:
        st.success("✅ **NOMINAL**: No significant multi-vector anomalies detected. Sector remains within standard 7-day variance.")
    
    st.markdown("---")
    st.markdown("### 📜 Mission Logs")
    st.code(f"""
[SCAN] Sector: {st.session_state.target_base}
[DATA] Acoustic Weight: {infra_score:.2f}
[DATA] Electronic Weight: {mag_score:.2f}
[DATA] Social Weight: {corvid_score:.2f}
[CALC] Unified RPI: {rpi_percent}%
[SYS] Scan Complete
    """, language="text")

st.markdown("### 🛠️ Deploy The Eyes")
c1, c2, c3 = st.columns(3)
if c1.button("🔊 Infrasound Eye", width='stretch'): st.switch_page("routes/infrasound_flush.py")
if c2.button("🧲 Magnetic Eye", width='stretch'): st.switch_page("routes/magnetic_static.py")
if c3.button("🐦‍⬛ Corvid Eye", width='stretch'): st.switch_page("routes/corvid_shadow.py")