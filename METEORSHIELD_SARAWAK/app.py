import streamlit as st
import numpy as np
import folium
from streamlit_folium import st_folium
import requests
import google.generativeai as genai
from fpdf import FPDF
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import pandas as pd
import rasterio
import quiz_page
from Asteroid_Launcher_Mode import show_launcher_mode
from pathlib import Path

#testing cobaannnnnn
#cubaan kedua testing
#cobaannnnn ketiga

# ----------------------------
# Environment Setup
# ----------------------------
load_dotenv()

# Gemini
GEMINI_KEY = os.getenv("GEMINI_KEY")
if not GEMINI_KEY:
    st.error("⚠️ No Gemini API key found. Please set GEMINI_KEY in your .env file.")
else:
    genai.configure(api_key=GEMINI_KEY)
    gemini_model = genai.GenerativeModel("models/gemini-2.5-flash")

# NASA
NASA_API_KEY = os.getenv("NASA_KEY", "DEMO_KEY")
if NASA_API_KEY == "DEMO_KEY":
    st.warning("⚠️ Using NASA DEMO_KEY (rate limited). Add NASA_KEY in .env for full access.")

dem_path = os.path.join("data", "sarawak_dem.tif")
if os.path.exists(dem_path):
    dem = rasterio.open(dem_path)
else:
    st.warning("⚠️ DEM file not found. Tsunami modeling will use rough estimates.")
    dem = None

# ----------------------------
# Functions
# ----------------------------
def get_nasa_asteroids(api_key="DEMO_KEY", days=3):
    """
    Fetch asteroid approach data from NASA NEO Feed API.
    Returns a list of upcoming asteroids within given days.
    """
    start_date = datetime.today().strftime("%Y-%m-%d")
    end_date = (datetime.today() + timedelta(days=days)).strftime("%Y-%m-%d")
    url = f"https://api.nasa.gov/neo/rest/v1/feed?start_date={start_date}&end_date={end_date}&api_key={api_key}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        neos = []
        for date, objs in data.get("near_earth_objects", {}).items():
            for obj in objs:
                neos.append(obj)
        return neos

    except requests.exceptions.HTTPError as e:
        if response.status_code == 429:
            st.error("⚠️ NASA API rate limit reached. Please wait a minute and try again.")
        else:
            st.error(f"⚠️ NASA API request failed: {e}")
        return []
    except Exception as e:
        st.error(f"⚠️ Unexpected NASA API error: {e}")
        return []

def get_neo_details(neo_id, api_key="DEMO_KEY"):
    """
    Fetch full NEO (Near Earth Object) details including orbital elements.
    """
    url = f"https://api.nasa.gov/neo/rest/v1/neo/{neo_id}?api_key={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"⚠️ Error fetching NEO details: {e}")
        return None

def extract_orbital_elements(neo_json):
    if not neo_json:
        return {}
    orbital = neo_json.get("orbital_data", {})
    return {
        "designation": neo_json.get("designation"),
        "name": neo_json.get("name"),
        "absolute_magnitude_h": neo_json.get("absolute_magnitude_h"),
        "estimated_diameter_m_min": neo_json.get("estimated_diameter", {}).get("meters", {}).get("estimated_diameter_min"),
        "estimated_diameter_m_max": neo_json.get("estimated_diameter", {}).get("meters", {}).get("estimated_diameter_max"),
        "orbit_semi_major_axis_au": orbital.get("semi_major_axis"),
        "orbit_eccentricity": orbital.get("eccentricity"),
        "orbit_inclination_deg": orbital.get("inclination"),
        "orbit_perihelion_au": orbital.get("perihelion_distance"),
        "orbit_aphelion_au": orbital.get("aphelion_distance"),
        "orbit_id": orbital.get("orbit_id"),
    }

def impact_energy(diameter_m, velocity_ms, density=3000):
    radius = diameter_m / 2
    volume = (4/3) * np.pi * radius**3
    mass = volume * density
    return 0.5 * mass * velocity_ms**2

def blast_radius(energy_joules):
    return (energy_joules ** (1/3)) / 1e5

def people_affected(radius_km, population_density=150):
    area = np.pi * (radius_km**2)
    return int(area * population_density)

def crater_size(energy_joules):
    """
    Estimate crater diameter and depth (simplified Holsapple scaling laws).
    """
    diameter_km = 1.8 * ((energy_joules / 4.2e15) ** 0.3)  # TNT scaling
    depth_km = diameter_km / 5
    return diameter_km, depth_km

def seismic_magnitude(energy_joules):
    """
    Estimate equivalent seismic magnitude (Richter scale).
    """
    return 0.67 * np.log10(energy_joules) - 5.87

def tsunami_wave_height(energy_joules, distance_km):
    """
    Estimate tsunami wave height for ocean impacts.
    """
    water_energy = 0.25 * energy_joules
    height = (water_energy ** 0.25) / (distance_km ** 0.5) / 50
    return max(height, 0)

def get_elevation(lat, lon, dem):
    """Return elevation in meters for given lat/lon."""
    if not dem:
        return 0
    try:
        for val in dem.sample([(lon, lat)]):
            return val[0]
    except:
        return 0

def tsunami_inundation(elevation_m, energy_joules):
    """Estimate tsunami radius based on elevation and impact energy."""
    base_radius_km = (energy_joules ** 0.25) / 50
    inundation_distance_km = max(base_radius_km - elevation_m / 10, 0)
    return inundation_distance_km

def propagate_orbit(a_au, e, i_deg, num_points=300):
    """
    Generate (x,y) positions of the asteroid orbit in AU using simple Kepler ellipse.
    a_au: semi-major axis in AU
    e: eccentricity
    i_deg: inclination in degrees (not applied here, just placeholder for later 3D)
    """
    if not a_au or not e:
        return [], []
    
    theta = np.linspace(0, 2*np.pi, num_points)
    r = (a_au * (1 - e**2)) / (1 + e * np.cos(theta))
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    return x, y

def adjusted_impact_velocity(velocity, delta_v, lead_time_days):
    return velocity - delta_v * (lead_time_days / 365)

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def estimate_tsunami_risk(city, radius_km):
    """
    Simple tsunami risk estimate using rough elevation values.
    Later: replace with USGS/SRTM elevation raster.
    """
    low_elevation_cities = {"Kuching": 27, "Sibu": 35, "Miri": 20, "Bintulu": 15}
    if city in low_elevation_cities:
        elev = low_elevation_cities[city]
        if elev < 50 and radius_km > 20:
            return f"🌊 Tsunami risk detected near {city} (elevation {elev}m)"
    return "No significant tsunami risk"

def get_usgs_earthquakes(lat, lon, radius_km=1000, days=30):
    """
    Fetch recent earthquakes from USGS NEIC Earthquake Catalog API.
    Returns events within given radius (km) and time window (days).
    """
    import requests
    from datetime import datetime, timedelta

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    url = (
        "https://earthquake.usgs.gov/fdsnws/event/1/query?"
        f"format=geojson&starttime={start_time.strftime('%Y-%m-%d')}"
        f"&endtime={end_time.strftime('%Y-%m-%d')}"
        f"&latitude={lat}&longitude={lon}&maxradiuskm={radius_km}"
    )

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        events = []
        for feature in data.get("features", []):
            props = feature["properties"]
            geom = feature["geometry"]
            events.append({
                "time": props.get("time"),
                "place": props.get("place", "Unknown"),
                "mag": props.get("mag"),
                "lat": geom["coordinates"][1],
                "lon": geom["coordinates"][0],
                "depth": geom["coordinates"][2],
            })
        return events
    except Exception as e:
        st.error(f"⚠️ Error fetching USGS Earthquake data: {e}")
        return []
    
def energy_gauge_chart(energy_joules):
    """
    Animated gauge chart for impact energy in TNT equivalent.
    Color changes from green to red with increasing energy.
    """
    tnt_equiv_mt = energy_joules / 4.184e15  # Convert Joules → Megatons TNT
    color = "green"
    if tnt_equiv_mt > 1000:
        color = "red"
    elif tnt_equiv_mt > 100:
        color = "orange"
    elif tnt_equiv_mt > 10:
        color = "yellow"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=tnt_equiv_mt,
            title={"text": "Impact Energy (Megatons TNT)"},
            delta={"reference": 0, "increasing": {"color": "red"}},
            gauge={
                "axis": {"range": [None, 10000]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 10], "color": "green"},
                    {"range": [10, 100], "color": "yellow"},
                    {"range": [100, 1000], "color": "orange"},
                    {"range": [1000, 10000], "color": "red"},
                ],
            },
        )
    )
    fig.update_layout(height=300, margin=dict(t=30, b=10, l=10, r=10))
    return fig

def generate_summary(asteroid_name, city, energy, radius, mitigation_method=None, original_energy=None):
    prompt = f"""
    Summarize this asteroid impact scenario near {city}.
    Asteroid: {asteroid_name}
    Impact energy: {energy:.2e} J
    Blast radius: {radius:.1f} km
    Mitigation: {mitigation_method or 'None'}

    Please provide short comparison:
    1) Outcome WITHOUT mitigation ({original_energy:.2e} J if available)
    2) Outcome WITH the selected mitigation
    Keep under 5 sentences, simple language.
    """
    try:
        result = gemini_model.generate_content(prompt)
        return result.text
    except Exception as e:
        return f"⚠️ AI summary error: {e}"

def generate_plan(city, radius):
    prompt = f"""
    Suggest a short emergency preparedness plan for Sarawak given an asteroid impact near {city}.
    Blast radius is about {radius:.1f} km.  

    Include 3–4 practical steps for:
    - Local authorities
    - Public awareness
    - Environmental protection
    """
    try:
        result = gemini_model.generate_content(prompt)
        return result.text
    except:
        return "⚠️ Could not generate preparedness plan."

def export_pdf(asteroid, city, energy, radius, summary, plan, mitigation_method=None, city_data=None):
    pdf = FPDF()
    pdf.add_page()

    font_path = r"C:\Users\Predator\Downloads\METEORSHIELD_SARAWAK\notebooks\DejaVuSans.ttf"
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.add_font("DejaVu", "B", font_path, uni=True)
    else:
        raise FileNotFoundError("⚠️ DejaVuSans.ttf not found.")

    pdf.set_auto_page_break(auto=True, margin=15)

    def write_paragraph(pdf, text, width=None, line_height=6, indent=0, bullet=False):
        if width is None:
            width = pdf.w - 2*pdf.l_margin
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                pdf.ln(line_height)
            else:
                prefix = "• " if bullet else ""
                pdf.multi_cell(width, line_height, " " * indent + prefix + line)

    # Title
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 12, "🌍 MeteorShield Sarawak - Impact Report", ln=True, align="C")
    pdf.ln(8)

    # Asteroid Info
    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, "Asteroid Information", ln=True)
    pdf.set_font("DejaVu", "", 12)
    write_paragraph(pdf, f"Asteroid: {asteroid}")
    write_paragraph(pdf, f"Impact Location: {city}")
    write_paragraph(pdf, f"Energy: {energy:.2e} J")
    write_paragraph(pdf, f"Blast Radius: {radius:.1f} km")
    if mitigation_method:
        write_paragraph(pdf, f"Mitigation Method: {mitigation_method}")
    if city_data:
        write_paragraph(pdf, "Affected Cities:")
        for c in city_data:
            write_paragraph(pdf, f"- {c['City']}: Distance {c['Distance from Impact (km)']}, Affected: {c['Affected?']}")
    pdf.ln(5)

    # AI Summary
    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(0, 10, "1. AI Summary", ln=True)
    pdf.set_font("DejaVu", "", 12)
    write_paragraph(pdf, summary)
    pdf.ln(5)

    # Preparedness Plan
    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(0, 10, "2. Preparedness Plan", ln=True)
    pdf.set_font("DejaVu", "", 12)

    for line in plan.split("\n"):
        line = line.strip()
        if line.startswith("####"):
            pdf.set_font("DejaVu", "B", 12)
            pdf.cell(0, 8, line.replace("####", ""), ln=True)
            pdf.set_font("DejaVu", "", 12)
        elif line.startswith("*") or line.startswith("-"):
            write_paragraph(pdf, line[1:].strip(), indent=2, bullet=True)
        else:
            write_paragraph(pdf, line, indent=0)

    filename = "Impact_Report.pdf"
    pdf.output(filename)
    return filename

# ----------------------------
# Page Config
# ----------------------------
st.set_page_config(page_title="MeteorShield Sarawak", layout="wide")

# ----------------------------
# Sidebar Custom Design (Space Theme)
# ----------------------------
st.markdown("""
<style>

/* --- Sidebar container --- */
[data-testid="stSidebar"] {
    background: radial-gradient(circle at top left, #060b1a, #0c1635 80%);
    color: #e0e6f5;
    border: none !important;
    padding: 0;
}

/* --- Sidebar title --- */
[data-testid="stSidebar"] h1, 
[data-testid="stSidebar"] h2, 
[data-testid="stSidebar"] h3 {
    color: #cfd8ff;
    text-align: center;
    font-family: 'Orbitron', sans-serif;
    letter-spacing: 1px;
}

/* --- Remove the "Go to" label --- */
section[data-testid="stSidebar"] p:has(span) {
    display: none !important;
}

/* --- Hide the default radio buttons --- */
div[role="radiogroup"] input[type="radio"] {
    display: none !important;
}

/* --- Make each option a full-width clickable box --- */
div[role="radiogroup"] > label {
    width: 100%;
    display: block;
    padding: 14px 18px;
    margin: 3px 0;
    border-radius: 0;
    background: transparent;
    border: none;
    color: #d7e3ff;
    font-size: 15px;
    font-weight: 500;
    transition: all 0.3s ease;
    cursor: pointer;
}

/* --- Hover glow effect --- */
div[role="radiogroup"] > label:hover {
    background: rgba(108, 160, 255, 0.08);
    color: #ffffff;
    transform: translateX(5px);
}

/* --- Active page (no blue box, just subtle left bar) --- */
div[role="radiogroup"] input:checked + div {
    background: transparent !important;
    color: #ffffff !important;
    border-left: 3px solid #6ca0ff;
    box-shadow: none !important;
}

/* --- Remove margin on bullet icon area --- */
div[role="radiogroup"] > label > div:first-child {
    display: none !important;
}

/* --- Sidebar link & text styling --- */
[data-testid="stSidebar"] a, [data-testid="stSidebar"] p {
    color: #cfd8ff !important;
    font-size: 14px;
}

/* --- Scrollbar design --- */
::-webkit-scrollbar {
    width: 8px;
}
::-webkit-scrollbar-thumb {
    background: #3c4b80;
    border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover {
    background: #6ca0ff;
}

</style>
""", unsafe_allow_html=True)


st.sidebar.markdown("""
    <h1 style='text-align:center;font-size:30px; font-family:Orbitron, sans-serif; color:#6ca0ff;'>
        🚀 Navigation
    </h1>
    <p style='text-align:center; font-size:14px; color:#a5b8ff;'>
        Explore the universe of data 🌠
    </p>
""", unsafe_allow_html=True)

page = st.sidebar.radio(
    "Go to",
    ["Main Page", "Impact Simulation", "Asteroid Launcher Mode", "Learning & Quiz"]
)

# ----------------------------
# Main Page
# ----------------------------
if page == "Main Page":
    st.markdown("<h1 style='text-align: center;'>🌍 MeteorShield Sarawak</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; font-size:18px;'>Welcome to MeteorShield Sarawak.<br>"
        "This tool visualizes asteroid impacts in Sarawak using NASA data, physics models, and AI.<br>"
        "Go to the simulation page to begin.</p>",
        unsafe_allow_html=True
    )

elif page == "Learning & Quiz":
    quiz_page.run_quiz()

elif page == "Asteroid Launcher Mode":
    show_launcher_mode()


    # ----------------------------
    # Simulation Page
    # -----------------------------

elif page == "Impact Simulation":
    from simulation import run_simulation
    run_simulation(
        gemini_model,
        NASA_API_KEY,
        dem,
        get_nasa_asteroids,
        get_neo_details,
        extract_orbital_elements,
        impact_energy,
        blast_radius,
        people_affected,
        crater_size,
        seismic_magnitude,
        tsunami_wave_height,
        get_elevation,
        tsunami_inundation,
        propagate_orbit,
        adjusted_impact_velocity,
        haversine_km,
        estimate_tsunami_risk,
        energy_gauge_chart,
        generate_summary,
        generate_plan,
        export_pdf
    )