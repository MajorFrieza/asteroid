import streamlit as st
import numpy as np
import requests
import os

# --- helper functions ---
def load_lottie_url(url):
    try:
        r = requests.get(url)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def impact_energy(diameter_m, velocity_ms, density=3000):
    r = diameter_m / 2
    volume = (4/3) * np.pi * r**3
    mass = volume * density
    return 0.5 * mass * velocity_ms**2

def crater_size(energy_joules):
    diameter_km = 1.8 * ((energy_joules / 4.2e15) ** 0.3)
    depth_km = diameter_km / 5
    return diameter_km, depth_km

def seismic_magnitude(energy_joules):
    return 0.67 * np.log10(energy_joules) - 5.87

def tsunami_wave_height(energy_joules, distance_km=200):
    water_energy = 0.25 * energy_joules
    height = (water_energy ** 0.25) / (distance_km ** 0.5) / 50
    return max(height, 0)

# --- main launcher mode ---
def show_launcher_mode():
    st.title("🎮 Asteroid Launcher Mode")
    st.markdown("Click anywhere on the map to choose your impact location, then launch your asteroid!")

    # --- default impact point ---
    if "impact_point" not in st.session_state:
        st.session_state.impact_point = [2.5, 112.5]

    # --- select impact location ---
    import folium
    from streamlit_folium import st_folium

    # --- Map for selecting impact ---
    click_map = folium.Map(location=st.session_state.impact_point, zoom_start=4)
    click_data = st_folium(click_map, width=750, height=450, key="select_map")

    # Update impact point if map is clicked
    if click_data and click_data.get("last_clicked"):
        lat = click_data["last_clicked"]["lat"]
        lon = click_data["last_clicked"]["lng"]
        st.session_state.impact_point = [lat, lon]
        st.success(f"🌍 Impact location selected: {lat:.2f}, {lon:.2f}")

    # Draw updated marker in a separate map
    lat, lon = st.session_state.impact_point
    marker_map = folium.Map(location=[lat, lon], zoom_start=4)
    folium.Marker(
        [lat, lon],
        tooltip="Impact point",
        icon=folium.Icon(color="red")
    ).add_to(marker_map)
    st_folium(marker_map, width=750, height=450, key="marker_map")

    # Info about selected location
    st.info(f"Selected Impact Location: 🌍 **{lat:.2f}, {lon:.2f}**")

    # --- asteroid parameters ---
    diameter = st.slider("Asteroid Diameter (m)", 10, 2000, 500, step=10)
    velocity = st.slider("Velocity (km/s)", 5, 70, 25, step=1)
    
    # --- asteroid composition ---
    composition = st.selectbox(
        "Asteroid Composition",
        ["Iron", "Stone", "Carbon", "Comet", "Gold"]
    )

    # Map compositions to densities
    density_map = {"Iron": 7800, "Stone": 3000, "Carbon": 2200, "Comet": 600, "Gold": 19300}
    density = density_map[composition]

    # Map compositions to images (replace URLs with actual image URLs or local paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    composition_images = {
        "Iron": os.path.join(BASE_DIR, "..", "images", "iron.jpg"),
        "Stone": os.path.join(BASE_DIR, "..", "images", "stone.jpg"),
        "Carbon": os.path.join(BASE_DIR, "..", "images", "carbon.jpg"),
        "Comet": os.path.join(BASE_DIR, "..", "images", "comet.jpg"),
        "Gold": os.path.join(BASE_DIR, "..", "images", "gold.jpg"),
    }


    # Show asteroid image
    st.image(
        composition_images[composition],
        caption=f"{composition} Asteroid",
        width=300  
    )

    # --- impact angle ---
    angle = st.slider("Impact Angle (°)", 5, 90, 45, step=1)

    launch = st.button("🚀 Launch Asteroid")

    if launch:
        with st.spinner("Launching asteroid..."):
            import time
            time.sleep(2)  # simulate delay

        # --- compute physics ---
        energy = impact_energy(diameter, velocity * 1000, density) * np.sin(np.radians(angle))
        crater, _ = crater_size(energy)
        mag = seismic_magnitude(energy)
        tsunami = tsunami_wave_height(energy)

        # --- show Lottie explosion ---
        from streamlit_lottie import st_lottie
        with st.spinner("🚀 Launching asteroid and calculating impact..."):
            import time
            time.sleep(2)  # simulate loading time

        # --- insert JS falling asteroid + impact map ---
        import streamlit.components.v1 as components

        html_code = f"""
        <div id="map" style="height: 450px;"></div>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            var map = L.map('map').setView([{lat}, {lon}], 5);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19
            }}).addTo(map);

            // moving asteroid
            var asteroid = L.circleMarker([{lat+10}, {lon}], {{
                radius: 10,
                color: 'red',
                fillOpacity: 1
            }}).addTo(map);

            var targetLat = {lat};
            var currentLat = {lat+10};
            var step = 0.5;

            function animate() {{
                if (currentLat > targetLat) {{
                    currentLat -= step;
                    asteroid.setLatLng([currentLat, {lon}]);
                    requestAnimationFrame(animate);
                }} else {{
                    // crater & shockwave
                    L.circle([targetLat, {lon}], {{radius: {crater*1000}, color:'orange', fillOpacity:0.4}}).addTo(map);
                    L.circle([targetLat, {lon}], {{radius: {crater*3000}, color:'blue', fillOpacity:0.2}}).addTo(map);

                    // --- map legend ---
                    var legend = L.control({{position: 'bottomleft'}});
                    legend.onAdd = function(map) {{
                        var div = L.DomUtil.create('div', 'info legend');
                        div.innerHTML = `
                            <b>Map Legend</b><br>
                            <span style="color:red;">●</span> Impact location<br>
                            <span style="color:orange;">●</span> Crater zone (~{crater:.1f} km)<br>
                            <span style="color:blue;">●</span> Tsunami / Shockwave zone<br>
                            <span style="color:black;">●</span> Fireball / Heat zone
                        `;
                        div.style.background = 'white';
                        div.style.padding = '8px';
                        div.style.borderRadius = '5px';
                        return div;
                    }};
                    legend.addTo(map);
                }}
            }}
            animate();
        </script>
        """

        components.html(html_code, height=500)

        # --- impact metrics ---
        st.markdown("### 📊 Impact Results")
        st.metric("💥 Energy Released", f"{energy/4.184e15:.2f} Mt TNT",
                delta="Equivalent to ~{} Hiroshima bombs".format(int(energy/6.3e13)))
        st.metric("🌋 Crater Diameter", f"{crater:.1f} km", delta="Approx. size of a small city")
        st.metric("🌊 Tsunami Height", f"{tsunami:.1f} m", delta="Can flood coastal areas")
        st.metric("🌐 Seismic Magnitude", f"M {mag:.2f}", delta="Earthquake felt over nearby regions")

# --- run app ---
show_launcher_mode()
