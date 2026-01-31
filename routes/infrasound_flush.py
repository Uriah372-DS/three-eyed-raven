import streamlit as st
import folium
from streamlit_folium import st_folium
from obspy.clients.fdsn import Client
from obspy import UTCDateTime
import numpy as np

# --- SETTINGS ---
st.title(f"🔊 The Infrasound Flush: {st.session_state.target_base}")

@st.cache_data(ttl=300)
def get_nearby_channels(lat, lon, channel="BDF", radius=1.0):
    client = Client("IRIS")
    try:
        inventory = client.get_stations(
            latitude=lat, longitude=lon, maxradius=radius, 
            level="channel", channel=channel,
            starttime=UTCDateTime.now() - 86400
        )
        return inventory
    except:
        return None

def get_raven_metrics(net, sta, loc="*", chan="BDF"):
    client = Client("IRIS")
    # Fetching slightly in the past to ensure data availability
    end = UTCDateTime.now() - 3600 
    start = end - 7200 # 2 hour window
    try:
        st_data = client.get_waveforms(net, sta, loc, chan, start, end)
        st_data.merge(method=1, fill_value='interpolate')
        tr = st_data[0]
        tr.detrend("linear").filter("bandpass", freqmin=0.5, freqmax=5.0)
        
        data = tr.data
        sampling_rate = tr.stats.sampling_rate
        last_hour_samples = int(3600 * sampling_rate)
        
        full_window_rms = np.sqrt(np.mean(data**2))
        recent_rms = np.sqrt(np.mean(data[-last_hour_samples:]**2))
        delta = ((recent_rms - full_window_rms) / full_window_rms) * 100
        return round(recent_rms, 2), round(delta, 1)
    except:
        return None, None

# --- MAP SECTION ---
lat, lon = st.session_state.active_lat, st.session_state.active_lon
m = folium.Map(location=[lat, lon], zoom_start=7)

# Target Marker
folium.Marker([lat, lon], popup="TARGET", icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")).add_to(m)

# Find Stations
inv = get_nearby_channels(lat, lon, channel="BDF", radius=2.0)
if inv:
    for network in inv:
        for station in network:
            folium.Marker(
                [station.latitude, station.longitude],
                popup=f"EYE: {network.code}.{station.code}",
                icon=folium.Icon(color="blue", icon="eye", prefix="fa")
            ).add_to(m)

st_folium(m, height=400, use_container_width=True)

# --- ANALYSIS ---
if inv:
    net, sta = inv[0].code, inv[0][0].code
    st.subheader(f"Signal Analysis: Station {sta} ({net})")
    with st.spinner("Decoding sub-audible pressure waves..."):
        intensity, delta = get_raven_metrics(net, sta)
    
    if intensity:
        c1, c2, c3 = st.columns(3)
        c1.metric("Acoustic Intensity", intensity, f"{delta}%")
        c2.metric("Anomaly Status", "FLUSH" if delta > 40 else "STABLE")
        c3.metric("Frequency Range", "0.5 - 5.0 Hz")
    else:
        st.warning("Station is active but current data stream is restricted.")
else:
    st.error("No Infrasound sensors found within range of target.")