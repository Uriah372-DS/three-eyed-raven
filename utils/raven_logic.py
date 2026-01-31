import streamlit as st
import requests
import nexradaws
import pyart
import pandas as pd
import numpy as np
from obspy.clients.fdsn import Client
from obspy import UTCDateTime
import os, shutil
from math import radians, cos, sin, asin, sqrt
import datetime

# --- SHARED UTILITIES ---
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return 2 * asin(sqrt(a)) * 6371

# --- EYE 1: INFRASOUND ---
@st.cache_data(ttl=300)
def fetch_infrasound_intel(lat, lon):
    client = Client("IRIS")
    try:
        inv = client.get_stations(latitude=lat, longitude=lon, maxradius=2.0, level="channel", channel="BDF")
        net, sta = inv[0].code, inv[0][0].code
        end = UTCDateTime.now() - 3600
        st_data = client.get_waveforms(net, sta, "*", "BDF", end - 7200, end)
        st_data.merge(method=1, fill_value='interpolate')
        tr = st_data[0]
        tr.detrend("linear").filter("bandpass", freqmin=0.5, freqmax=5.0)
        data = tr.data
        last_hour = int(len(data)/2)
        full_rms = np.sqrt(np.mean(data**2))
        recent_rms = np.sqrt(np.mean(data[-last_hour:]**2))
        delta = ((recent_rms - full_rms) / full_rms) * 100
        return {"intensity": round(recent_rms, 2), "delta": round(delta, 1), "station": f"{net}.{sta}", "inv": inv}
    except:
        return {"intensity": 0, "delta": 0, "station": "None", "inv": None}

# --- EYE 2: MAGNETIC (NEXRAD) ---
@st.cache_data(ttl=600)
def fetch_magnetic_intel(radar_id):
    conn = nexradaws.NexradAwsInterface()
    now = datetime.datetime.utcnow()
    try:
        scans = conn.get_avail_scans(now.year, now.month, now.day, radar_id)
        data_scans = [s for s in scans if not s.filename.endswith('_MDM')]
        temp_dir = f'temp_{radar_id}'
        if not os.path.exists(temp_dir): os.makedirs(temp_dir)
        res = conn.download(data_scans[-1], temp_dir)
        radar = pyart.io.read(res.success[0].filepath)
        
        sweep = 0
        start, end = radar.get_start(sweep), radar.get_end(sweep)
        ref = radar.fields['reflectivity']['data'][start:end].flatten()
        rho = radar.fields['cross_correlation_ratio']['data'][start:end].flatten()
        lat = radar.gate_latitude['data'][start:end].flatten()
        lon = radar.gate_longitude['data'][start:end].flatten()
        
        df = pd.DataFrame({'lat': lat, 'lon': lon, 'Ref': ref, 'Rho': rho}).dropna()
        df = df[(df['Ref'] >= 5) & (df['Ref'] <= 30)] # Filter for birds
        avg_rho = float(df['Rho'].mean())
        shutil.rmtree(temp_dir)
        return {"avg_rho": round(avg_rho, 3), "df": df.sample(min(len(df), 5000)) if not df.empty else df}
    except:
        return {"avg_rho": 0.985, "df": pd.DataFrame()}

# --- EYE 3: CORVID ---
@st.cache_data(ttl=3600)
def fetch_corvid_intel(lat, lon, api_key):
    url = "https://api.ebird.org/v2/data/obs/geo/recent"
    headers = {'X-eBirdApiToken': api_key}
    params = {'lat': lat, 'lng': lon, 'dist': 10, 'back': 7, 'fmt': 'json'}
    try:
        res = requests.get(url, headers=headers, params=params).json()
        df = pd.DataFrame(res)
        df = df[df['comName'].str.contains("Crow|Raven|Magpie|Jay|Corvus", case=False, na=False)]
        if df.empty: return {"ratio": 1.0, "total": 0, "df": df}
        
        df['dist'] = df.apply(lambda r: haversine(lon, lat, r['lng'], r['lat']), axis=1)
        base_c = df[df['dist'] <= 2]['howMany'].fillna(1).sum()
        sub_c = df[df['dist'] > 2]['howMany'].fillna(1).sum()
        ratio = sub_c / base_c if base_c > 0 else 1.0
        return {"ratio": round(ratio, 2), "total": int(base_c + sub_c), "df": df}
    except:
        return {"ratio": 1.0, "total": 0, "df": pd.DataFrame()}