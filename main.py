import streamlit as st
import pandas as pd
import os

# Set page config FIRST
st.set_page_config(
    page_title="The Three-Eyed Raven",
    page_icon="🐦‍⬛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DATA INITIALIZATION ---
if "bases" not in st.session_state:
    # Fallback if file missing for demo purposes
    if os.path.exists("data/bases.csv"):
        st.session_state.bases = pd.read_csv("data/bases.csv", index_col="Base").to_dict(orient="index")
    else:
        st.session_state.bases = {
            "Pentagon": {"Latitude": 38.8710, "Longitude": -77.0560, "Radar_ID": "KLWX"},
            "Whiteman AFB": {"Latitude": 38.7303, "Longitude": -93.5479, "Radar_ID": "KEAX"}
        }

if "target_base" not in st.session_state:
    st.session_state.target_base = list(st.session_state.bases.keys())[0]

# --- SIDEBAR TARGETING ---
st.sidebar.title("🐦‍⬛ 3ER COMMAND")
selected = st.sidebar.selectbox(
    "Select Target Base", 
    options=list(st.session_state.bases.keys()), 
    index=list(st.session_state.bases.keys()).index(st.session_state.target_base)
)

if selected != st.session_state.target_base:
    st.session_state.target_base = selected
    # Update global coords for sub-pages
    st.session_state.active_lat = st.session_state.bases[selected]['Latitude']
    st.session_state.active_lon = st.session_state.bases[selected]['Longitude']
    st.session_state.active_radar = st.session_state.bases[selected].get('Radar_ID', 'KLWX')
    st.rerun()

# Sync current base data to state for sub-page access
st.session_state.active_lat = st.session_state.bases[st.session_state.target_base]['Latitude']
st.session_state.active_lon = st.session_state.bases[st.session_state.target_base]['Longitude']
st.session_state.active_radar = st.session_state.bases[st.session_state.target_base].get('Radar_ID', 'KLWX')

# --- NAVIGATION ---
pg = st.navigation({
    "Central Command": [st.Page("routes/home.py", title="The Raven's Nest", icon="🏰", default=True)],
    "The Three Eyes": [
        st.Page("routes/infrasound_flush.py", title="The Infrasound Flush", icon="🔊"),
        st.Page("routes/magnetic_static.py", title="The Magnetic Static", icon="🧲"),
        st.Page("routes/corvid_shadow.py", title="The Corvid Shadow", icon="🐦‍⬛")
    ]
})

pg.run()