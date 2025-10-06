import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
import requests

# ==============================
# IMPACT SIMULATION PAGE (TABBED LAYOUT)
# ==============================

def run_simulation(
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
):
    """
    Main function to run the Impact Simulation page with tabbed layout
    """

    st.title("☄️ Asteroid Impact Simulation Dashboard")

    # --- Create Tabs ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🪐 Asteroid Input",
        "🚀 Mitigation Planning",
        "💥 Impact Analysis",
        "🌊 Impact Visualization",
        "🤖 AI Insights & Report"
    ])

    # =======================================================
    # TAB 1 — ASTEROID INPUT (Move all NASA/custom input logic here)
    # =======================================================
    with tab1:
        st.subheader("Asteroid Input")
        mode = st.radio("Input Mode", ["NASA Data", "Custom Scenario"])

        diameter = None
        velocity = None
        selected = None
        approach_date = None

        # ----------------------------
        # NASA Data Mode
        # ----------------------------
        if mode == "NASA Data":
            # extend to 7 days forecast
            asteroids = get_nasa_asteroids(NASA_API_KEY, days=7)

            if not asteroids:
                st.error("⚠️ No asteroid data available. Check NASA API or try later.")
            else:
                # Separate hazardous vs non-hazardous
                hazardous = [a for a in asteroids if a.get("is_potentially_hazardous_asteroid")]
                normal = [a for a in asteroids if not a.get("is_potentially_hazardous_asteroid")]

                # Show warning if hazardous exist
                if hazardous:
                    st.warning(f"⚠️ {len(hazardous)} potentially hazardous asteroid(s) detected in the next 7 days!")

                # Build selection list (hazardous marked with 🚨)
                options = []
                for a in hazardous:
                    options.append((f"🚨 {a.get('name','Unknown')} (id:{a.get('id')})", a.get("id")))
                for a in normal:
                    options.append((f"{a.get('name','Unknown')} (id:{a.get('id')})", a.get("id")))

                display_names = [d for d, _ in options]
                selected_display = st.selectbox("Choose Asteroid", display_names)
                selected_id = options[display_names.index(selected_display)][1]

                asteroid_data = get_neo_details(selected_id, api_key=NASA_API_KEY)
                if asteroid_data:
                    orbital = extract_orbital_elements(asteroid_data)

                    # NASA Orbital Table
                    st.markdown("### NASA Orbital Elements")
                    st.table({
                        "Parameter": [
                            "Name", "Absolute Magnitude (H)", "Diameter (m)", "Semi-major axis (AU)",
                            "Eccentricity", "Inclination (deg)", "Perihelion (AU)", "Aphelion (AU)", "Orbit ID"
                        ],
                        "Value": [
                            orbital.get("name"),
                            orbital.get("absolute_magnitude_h"),
                            f"{orbital.get('estimated_diameter_m_min'):.1f} - {orbital.get('estimated_diameter_m_max'):.1f}" if orbital.get("estimated_diameter_m_min") else "N/A",
                            orbital.get("orbit_semi_major_axis_au"),
                            orbital.get("orbit_eccentricity"),
                            orbital.get("orbit_inclination_deg"),
                            orbital.get("orbit_perihelion_au"),
                            orbital.get("orbit_aphelion_au"),
                            orbital.get("orbit_id")
                        ]
                    })

                    # ----------------------------
                    # 2D Orbit Plot 
                    # ----------------------------
                    if orbital.get("orbit_semi_major_axis_au") and orbital.get("orbit_eccentricity"):
                        try:
                            a = float(orbital["orbit_semi_major_axis_au"])
                            e = float(orbital["orbit_eccentricity"])
                            i = float(orbital.get("orbit_inclination_deg") or 0)
                            x2d, y2d = propagate_orbit(a, e, i)

                            fig, ax = plt.subplots(figsize=(5, 5))

                            # Asteroid orbit
                            ax.plot(x2d, y2d, color="red", label=f"{selected} Orbit (Asteroid)")

                            # Earth orbit (reference circle)
                            theta = np.linspace(0, 2*np.pi, 300)
                            ax.plot(np.cos(theta), np.sin(theta), linestyle="--", color="blue", label="Earth’s Orbit")

                            # Sun in center
                            ax.scatter([0], [0], color="yellow", s=200, marker="o", label="☀️ Sun")
                            ax.text(0, 0, "Sun", fontsize=10, ha="center", va="bottom", color="gold")

                            ax.set_aspect("equal")
                            ax.set_xlabel("X (Astronomical Units)")
                            ax.set_ylabel("Y (Astronomical Units)")
                            ax.set_title("🌌 Top-Down View of Asteroid vs Earth Orbits")
                            ax.legend(loc="upper right")
                            ax.grid(True)
                            st.pyplot(fig)

                            st.info("""
                            **How to Read This:**
                            - ☀️ **Yellow dot** = the Sun (center of our solar system)  
                            - 🔵 **Blue dashed circle** = Earth’s orbit  
                            - 🔴 **Red oval** = Asteroid’s orbit  
                            When the red orbit crosses the blue circle, a **possible close approach or impact** can occur.
                            """)

                        except Exception as e:
                            st.warning(f"⚠️ Could not generate 2D orbit plot: {e}")

                    # ----------------------------
                    # 3D Orbit Visualization (Corrected: Sun static + Earth & Asteroid animate; speed slider)
                    # ----------------------------
                    st.subheader("🌌 Animated 3D Orbit Visualization")

                    # animation speed (ms per frame)
                    orbit_speed = st.slider(
                        "🌠 Orbit Animation Speed (ms per frame, lower → faster)",
                        min_value=10, max_value=300, value=60, step=10
                    )

                    # number of animation steps (fewer = smoother on slower machines)
                    FRAME_COUNT = 120

                    # Only run if we have orbital params (a,e) available
                    try:
                        # make sure a, e, i exist (from NASA or user inputs)
                        if not (a and e):
                            raise ValueError("Orbit parameters missing (semi-major axis or eccentricity).")

                        theta = np.linspace(0, 2*np.pi, FRAME_COUNT)
                        r = (a * (1 - e**2)) / (1 + e * np.cos(theta))
                        i_rad = np.radians(i if i is not None else 0.0)

                        # Asteroid coordinates (tilted)
                        x_ast = r * np.cos(theta)
                        y_ast = r * np.sin(theta) * np.cos(i_rad)
                        z_ast = r * np.sin(theta) * np.sin(i_rad)

                        # Earth orbit coordinates (1 AU circle in xy-plane)
                        x_earth = np.cos(theta)
                        y_earth = np.sin(theta)
                        z_earth = np.zeros_like(theta)

                        # --- Build frames that ONLY update the first 4 traces:
                        # trace0: asteroid_trail (lines)
                        # trace1: asteroid_marker (marker)
                        # trace2: earth_trail (lines)
                        # trace3: earth_marker (marker)
                        frames = []
                        for step in range(len(theta)):
                            frames.append(go.Frame(
                                data=[
                                    # asteroid trail up to this step
                                    go.Scatter3d(x=x_ast[:step+1], y=y_ast[:step+1], z=z_ast[:step+1],
                                                mode="lines", line=dict(color="red", width=4), name="Asteroid Trail"),

                                    # asteroid current position
                                    go.Scatter3d(x=[x_ast[step]], y=[y_ast[step]], z=[z_ast[step]],
                                                mode="markers", marker=dict(size=6, color="red"), name="Asteroid"),

                                    # earth trail up to this step
                                    go.Scatter3d(x=x_earth[:step+1], y=y_earth[:step+1], z=z_earth[:step+1],
                                                mode="lines", line=dict(color="blue", width=3, dash="dash"), name="Earth Trail"),

                                    # earth current position + label
                                    go.Scatter3d(x=[x_earth[step]], y=[y_earth[step]], z=[z_earth[step]],
                                                mode="markers+text",
                                                marker=dict(size=6, color="blue"),
                                                text=["🌍 Earth"], textposition="top center",
                                                name="Earth")
                                ],
                                name=f"frame{step}"
                            ))

                        # --- Base figure: put updatable traces FIRST (they will be overwritten by frames),
                        # and put static traces (full orbit lines, Sun) AFTER so frames DON'T overwrite them.
                        base_traces = [
                            # 0. asteroid_trail (initialized empty / single point)
                            go.Scatter3d(x=[x_ast[0]], y=[y_ast[0]], z=[z_ast[0]],
                                        mode="lines", line=dict(color="red", width=4), name="Asteroid Trail"),
                            # 1. asteroid_marker
                            go.Scatter3d(x=[x_ast[0]], y=[y_ast[0]], z=[z_ast[0]],
                                        mode="markers", marker=dict(size=6, color="red"), name="Asteroid"),
                            # 2. earth_trail
                            go.Scatter3d(x=[x_earth[0]], y=[y_earth[0]], z=[z_earth[0]],
                                        mode="lines", line=dict(color="blue", width=3, dash="dash"), name="Earth Trail"),
                            # 3. earth_marker
                            go.Scatter3d(x=[x_earth[0]], y=[y_earth[0]], z=[z_earth[0]],
                                        mode="markers+text",
                                        marker=dict(size=6, color="blue"),
                                        text=["🌍 Earth"], textposition="top center",
                                        name="Earth"),
                            # 4. Earth static full orbit (kept static so always visible)
                            go.Scatter3d(x=x_earth, y=y_earth, z=z_earth,
                                        mode="lines", line=dict(color="lightblue", width=1), name="Earth Orbit", showlegend=True),
                            # 5. Asteroid static full orbit (kept static for context)
                            go.Scatter3d(x=x_ast, y=y_ast, z=z_ast,
                                        mode="lines", line=dict(color="pink", width=1), name=f"{selected} Orbit", showlegend=True),
                            # 6. Sun - static, last trace so frames won't replace it
                            go.Scatter3d(x=[0], y=[0], z=[0],
                                        mode="markers+text",
                                        marker=dict(size=14, color="yellow"),
                                        text=["☀️ Sun"], textposition="top center",
                                        name="Sun")
                        ]

                        fig3d = go.Figure(data=base_traces,
                                        layout=go.Layout(
                                            title=f"Animated 3D Orbit: {selected}",
                                            scene=dict(
                                                xaxis_title="X (AU)",
                                                yaxis_title="Y (AU)",
                                                zaxis_title="Z (AU)",
                                                aspectmode="data"
                                            ),
                                            margin=dict(l=0, r=0, b=0, t=30),
                                            updatemenus=[dict(
                                                type="buttons",
                                                showactive=False,
                                                buttons=[
                                                    dict(label="▶ Play", method="animate",
                                                        args=[None, {"frame": {"duration": orbit_speed, "redraw": True},
                                                                        "fromcurrent": True, "mode": "immediate"}]),
                                                    dict(label="⏸ Pause", method="animate",
                                                        args=[[None], {"frame": {"duration": 0}, "mode": "immediate"}])
                                                ],
                                                x=0.0, y=0.05
                                            )]
                                        ),
                                        frames=frames)

                        st.plotly_chart(fig3d, use_container_width=True)

                        st.info("""
                        ### 🪐 How to read this:
                        - ☀️ Sun is shown as a yellow marker in the center and remains visible.  
                        - 🌍 Earth orbits in blue (static full orbit for context and a moving blue marker).  
                        - 🔴 Asteroid orbit is pink (static) with a moving red marker and a trailing red path.
                        - Use the slider to control animation speed.
                        """)

                    except Exception as e:
                        st.warning(f"⚠️ Could not generate animated 3D orbit visualization: {e}")

                    # Diameter & Velocity Extraction
                    diameter = asteroid_data.get("estimated_diameter", {}).get("meters", {}).get("estimated_diameter_max")
                    close_data = asteroid_data.get("close_approach_data")
                    if close_data and len(close_data) > 0:
                        velocity = float(close_data[0]["relative_velocity"]["kilometers_per_second"]) * 1000
                        approach_date = close_data[0].get("close_approach_date", "N/A")
                    else:
                        velocity = None
                        approach_date = "N/A"

                    if not diameter or not velocity:
                        st.warning("⚠️ Missing NASA data. Enter custom values.")
                        selected = st.text_input("Asteroid Name", asteroid_data.get("name", "Custom Asteroid"))
                        diameter = st.slider("Diameter (m)", 10, 1000, 150)
                        velocity = st.slider("Velocity (km/s)", 5, 70, 20) * 1000
                        approach_date = "N/A"
                    else:
                        selected = orbital.get("name")
                else:
                    st.error("⚠️ Could not load asteroid details. Switching to Custom Scenario.")
                    selected = st.text_input("Asteroid Name", "Custom Asteroid")
                    diameter = st.slider("Diameter (m)", 10, 1000, 150)
                    velocity = st.slider("Velocity (km/s)", 5, 70, 20) * 1000
                    approach_date = "N/A"

        # ----------------------------
        # Custom Scenario Mode
        # ----------------------------
        elif mode == "Custom Scenario":
            selected = st.text_input("Asteroid Name", "Custom Asteroid")
            diameter = st.slider("Diameter (m)", 10, 1000, 150)
            velocity = st.slider("Velocity (km/s)", 5, 70, 20) * 1000
            approach_date = "N/A"

    # =======================================================
    # TAB 2 — MITIGATION PLANNING (move deflection logic here)
    # =======================================================
    with tab2:
        # ----------------------------
        # Phase 2: Mitigation
        # ----------------------------
        st.subheader("Mitigation Options")

        lead_time_days = st.slider(
            "Lead Time before Impact (days)",
            min_value=1,
            max_value=365,
            value=30,
            help="Days before impact to attempt deflection"
        )

        # Choose mitigation method
        mitigation_method = st.selectbox(
            "Select Mitigation Method",
            ["Kinetic Impactor", "Nuclear Deflection", "Gravity Tractor", "Laser Ablation"]
        )

        # Base ΔV
        delta_v = st.slider(
            "Base ΔV (m/s)",
            min_value=0,
            max_value=100,
            value=10,
            help="Velocity change applied (before mitigation scaling)"
        )

        # Apply multiplier depending on method
        if mitigation_method == "Nuclear Deflection":
            delta_v *= 5   # very strong
        elif mitigation_method == "Gravity Tractor":
            delta_v *= 0.5  # weaker but continuous
        elif mitigation_method == "Laser Ablation":
            delta_v *= 1.5  # medium effectiveness
        # Kinetic Impactor keeps base ΔV

        if velocity:
            velocity_adjusted = adjusted_impact_velocity(velocity, delta_v, lead_time_days)
        else:
            velocity_adjusted = velocity

    # =======================================================
    # TAB 3 — IMPACT ANALYSIS (move impact results and charts here)
    # =======================================================
    with tab3:
       # ----------------------------
        # Impact Energy Section
        # ----------------------------
        
        # Calculate energy & blast radius
        if diameter and velocity:
            energy = impact_energy(diameter, velocity_adjusted)
            radius = blast_radius(energy)
        else:
            st.error("⚠️ Missing asteroid diameter or velocity to compute impact energy.")
            energy, radius = 0, 0

        st.subheader("💥 Impact Energy")

        # Convert Joules → Megatons TNT
        tnt_mt = energy / 4.184e15   # J → MT TNT
        hiroshima_eq = (tnt_mt * 1e6) / 15_000   # Hiroshima ~15 kt
        tsar_eq = tnt_mt / 50   # Tsar Bomba ~50 Mt
        chelyabinsk_eq = tnt_mt / 0.5   # Chelyabinsk ~0.5 Mt

        # Plain English summary
        st.info(f"""
        ### 🌍 Plain English Impact Scale
        - Impact Energy ≈ **{tnt_mt:,.1f} megatons TNT**  
        - Equivalent to **{hiroshima_eq:,.0f} Hiroshima bombs**  
        - Or about **{tsar_eq:,.1f} Tsar Bombas**  
        - (For context: Chelyabinsk 2013 was ~0.5 Mt)
        """)

        # Technical charts (for experts)
        with st.expander("🔬 See detailed energy charts"):
            st.plotly_chart(energy_gauge_chart(energy), use_container_width=True)

            # Historical comparison
            benchmarks = {
                "Hiroshima Bomb (~15 kt)": 6.3e13,
                "Nagasaki Bomb (~20 kt)": 8.4e13,
                "Tsar Bomba (50 Mt)": 2.1e17,
                "Chelyabinsk (2013)": 4.2e15,
                "Tunguska (1908)": 6.3e16,
            }

            energies = list(benchmarks.values()) + [energy]
            labels = list(benchmarks.keys()) + [f"{selected} Impact"]

            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=labels,
                y=energies,
                text=[f"{e:.2e}" for e in energies],
                textposition="outside"
            ))
            fig_bar.update_layout(
                yaxis_type="log",
                title="Asteroid Impact Energy vs Historical Explosions",
                xaxis_title="Event",
                yaxis_title="Energy (J, log scale)"
            )
            st.plotly_chart(fig_bar, use_container_width=True)
            st.caption("Technical charts compare impact energy against historical nuclear tests and asteroid events.")

            # Dynamic risk message
            risk_level = "🟢 Low"
            if energy > 1e17:
                risk_level = "🟡 Moderate"
            if energy > 1e18:
                risk_level = "🟠 High"
            if energy > 1e19:
                risk_level = "🔴 Extreme"

            st.markdown(
                f"<h4 style='color:{'red' if 'Extreme' in risk_level else 'orange' if 'High' in risk_level else 'green'};'>"
                f"Risk Level: {risk_level}</h4>",
                unsafe_allow_html=True,
            )

            # Pulse animation for blast radius text
            blast_html = f"""
            <div style="animation: pulse 1s ease-in-out; color:#f39c12; font-weight:bold;">
                Updated Blast Radius: {radius:.2f} km
            </div>
            <style>
            @keyframes pulse {{
                0% {{ opacity: 0.3; }}
                50% {{ opacity: 1; }}
                100% {{ opacity: 0.3; }}
            }}
            </style>
            """
            st.markdown(blast_html, unsafe_allow_html=True)

            # --- Single city dropdown (existing feature) ---
            st.markdown("### 🎯 Select Impact Location")
            locations = {
                "Kuching": [1.55, 110.33],
                "Sibu": [2.29, 111.83],
                "Miri": [4.40, 113.99],
                "Bintulu": [3.17, 113.03],
            }
            city = st.selectbox("Impact Location", list(locations.keys()))
            lat, lon = locations[city]

            # ✅ NEW: Show tsunami risk
            tsunami_msg = estimate_tsunami_risk(city, radius)
            st.info(tsunami_msg)

            # --- Multi-city impact assessment (new feature) ---
            st.markdown("### 🌍 Multi-city Impact Assessment")
            st.info("Enter city coordinates (lat, lon). Compare which ones fall within the blast radius.")

            cities_input = st.text_area(
                "Enter cities (format: CityName, lat, lon per line)",
                "Kuching, 1.55, 110.33\nSibu, 2.29, 111.83\nMiri, 4.40, 113.99\nBintulu, 3.17, 113.03\nKuala Lumpur, 3.1390, 101.6869\nSingapore, 1.3521, 103.8198"
            )

            city_data = []
            for line in cities_input.splitlines():
                try:
                    name, lat_c, lon_c = [x.strip() for x in line.split(",")]
                    lat_c, lon_c = float(lat_c), float(lon_c)

                    # Rough distance from selected impact city
                    distance = haversine_km(lat, lon, lat_c, lon_c)
                    affected = distance <= radius

                    city_data.append({
                        "City": name,
                        "Latitude": lat_c,
                        "Longitude": lon_c,
                        "Distance from Impact (km)": f"{distance:.1f}",
                        "Affected?": "Yes ✅" if affected else "No ❌"
                    })
                except:
                    continue

            if city_data:
                st.dataframe(pd.DataFrame(city_data))

                # Map of cities
                df_map = pd.DataFrame(city_data)
                st.map(df_map.rename(columns={"Latitude": "lat", "Longitude": "lon"}))

            # ----------------------------
            # Population & Decision-Support Summary
            # ----------------------------
            st.subheader("👥 Decision-Support Summary")

            # Estimate affected population based on blast radius
            estimated_people = people_affected(radius)

            # Calculate avoided damage if mitigation reduced energy
            original_energy = impact_energy(diameter, velocity) if diameter and velocity else None
            if original_energy:
                original_people = people_affected(blast_radius(original_energy))
                avoided = max(original_people - estimated_people, 0)
            else:
                avoided = None

            colA, colB, colC = st.columns(3)
            colA.metric("Estimated People Affected", f"{estimated_people:,}")
            colB.metric("Potentially Avoided (with Mitigation)", f"{avoided:,}" if avoided else "N/A")
            colC.metric("Preparedness Level", "Medium", help="Based on blast size & mitigation results")

            st.info(
                f"""
                📊 **Interpretation for Decision-Makers**  
                - Approx. **{estimated_people:,} people** may be within the blast radius.  
                - Mitigation could **save {avoided:,} lives** compared to a no-action scenario.  
                - Recommended to trigger preparedness planning immediately.
                """
            )    

    # =======================================================
    # TAB 4 — IMPACT VISUALIZATION (move Folium & Globe map here)
    # =======================================================
    with tab4:
        st.subheader("🌍 Global Impact Visualization")

        view_mode = st.radio(
            "Choose Visualization Mode",
            ["🌍 Globe (3D)", "🗺 Map (Leaflet)"],
            horizontal=True
        )

        # Calculate elevation, tsunami radius, and seismic magnitude
        elevation = get_elevation(lat, lon, dem)
        tsunami_radius = tsunami_inundation(elevation or 0, energy)
        eq_magnitude = seismic_magnitude(energy)

        # Load USGS Earthquake Data
        show_eq = st.checkbox("🌋 Show Regional Earthquake Activity (USGS)", value=True)
        eq_points = []
        if show_eq:
            try:
                usgs_url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_month.geojson"
                eq_data = requests.get(usgs_url, timeout=10).json()
                eq_points = [
                    {
                        "lat": f["geometry"]["coordinates"][1],
                        "lon": f["geometry"]["coordinates"][0],
                        "mag": f["properties"]["mag"],
                        "place": f["properties"]["place"],
                    }
                    for f in eq_data["features"]
                    if 90 >= f["geometry"]["coordinates"][1] >= -90
                ]
            except Exception as e:
                st.warning(f"⚠️ Could not load USGS data: {e}")

        # Zones (blast, tsunami, seismic)
        zones = [
            {"radius": radius, "color": "red", "label": f"Blast Zone (~{radius:.1f} km)"},
            {"radius": tsunami_radius, "color": "blue", "label": f"Tsunami Zone (~{tsunami_radius:.1f} km)"},
            {"radius": 10 ** (eq_magnitude / 2), "color": "orange", "label": f"Seismic Zone (~{10 ** (eq_magnitude / 2):.1f} km)"}
        ]

        # -----------------------------
        # Globe mode
        # -----------------------------
        if view_mode == "🌍 Globe (3D)":
            fig = go.Figure()

            # Impact Point
            fig.add_trace(go.Scattergeo(
                lat=[lat], lon=[lon],
                mode="markers",
                marker=dict(size=14, color="gold", symbol="star"),
                name="Impact Point",
                text=[f"Impact at {city}"],
            ))

            # Hazard zones
            for z in zones:
                circle_points = []
                for angle in np.linspace(0, 2*np.pi, 200):
                    d = z["radius"] / 111  # km → degrees approx
                    circle_points.append((
                        lat + d * np.cos(angle),
                        lon + d * np.sin(angle) / np.cos(np.radians(lat))
                    ))
                lats, lons = zip(*circle_points)
                fill_color = {
                    "red": "rgba(255,0,0,0.3)",
                    "blue": "rgba(0,0,255,0.25)",
                    "orange": "rgba(255,165,0,0.25)"
                }.get(z["color"], "rgba(255,255,255,0.2)")
                fig.add_trace(go.Scattergeo(
                    lat=lats, lon=lons,
                    mode="lines",
                    fill="toself",
                    fillcolor=fill_color,
                    line=dict(width=2, color=z["color"]),
                    name=z["label"]
                ))

            # Earthquake markers
            if eq_points:
                fig.add_trace(go.Scattergeo(
                    lat=[e["lat"] for e in eq_points],
                    lon=[e["lon"] for e in eq_points],
                    text=[f"{e['place']}<br>Magnitude: {e['mag']}" for e in eq_points],
                    mode="markers",
                    marker=dict(size=[max(4, e["mag"] * 2) for e in eq_points],
                                color="orange", opacity=0.7),
                    name="Regional Earthquakes (USGS)"
                ))

            # Layout – globe-like projection
            fig.update_layout(
                title=dict(
                    text=f"🌎 Asteroid Impact Simulation – {city}",
                    x=0.5, y=0.95,
                    xanchor="center", yanchor="top",
                    font=dict(size=20)
                ),
                geo=dict(
                    showframe=False,
                    showcoastlines=True,
                    coastlinecolor="gray",
                    landcolor="rgb(230,230,230)",
                    showocean=True,
                    oceancolor="rgb(170,210,255)",
                    projection_type="orthographic",
                    center=dict(lat=lat, lon=lon),
                    projection_rotation=dict(lon=lon, lat=lat, roll=0),
                    showland=True,
                    showcountries=True,
                    resolution=110,
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.15,
                    xanchor="center",
                    x=0.5,
                    bgcolor="rgba(255,255,255,0.85)",
                    bordercolor="rgba(0,0,0,0.3)",
                    borderwidth=1,
                    font=dict(color="black", size=11)
                ),
                height=650,
                margin=dict(l=0, r=0, t=70, b=0)
            )

            st.plotly_chart(fig, use_container_width=True)

            # Public legend
            st.markdown("""
            ### 🧭 How to Read This Map
            - 🟡 **Star marker** → Asteroid impact location  
            - 🔴 **Red zone** → Severe blast and crater area  
            - 🟠 **Orange zone** → Seismic ground shaking area  
            - 🔵 **Blue zone** → Tsunami risk region  
            - 🟠 **Small orange dots** → Real earthquakes from USGS data  
            - 🌍 Drag to rotate the globe and zoom to inspect regions  
            """)

            # Earthquake table
            if eq_points:
                st.markdown("#### 🌋 Regional Earthquake Activity (Source: USGS)")
                df_eq = pd.DataFrame(eq_points)[["place", "mag", "lat", "lon"]].rename(
                    columns={"place": "Location", "mag": "Magnitude", "lat": "Latitude", "lon": "Longitude"}
                )
                st.dataframe(df_eq, use_container_width=True)

        # -----------------------------
        # Leaflet mode
        # -----------------------------
        elif view_mode == "🗺 Map (Leaflet)":
            # Checkbox toggle for mouse wheel zoom
            enable_wheel_zoom = st.checkbox("🖱 Enable Mouse Wheel Zoom", value=False)

            # Create Folium map
            m = folium.Map(
                location=[lat, lon],
                zoom_start=5,
                tiles="CartoDB positron",
                control_scale=True,
                zoom_control=True,               # +/– zoom buttons
                scrollWheelZoom=enable_wheel_zoom  # ✅ user can enable/disable wheel zoom
            )

            # Add interactive plugins
            from folium.plugins import Fullscreen, MeasureControl, MiniMap
            Fullscreen().add_to(m)           
            MeasureControl().add_to(m)       
            MiniMap(toggle_display=True).add_to(m)  
            folium.LayerControl().add_to(m)  

            # Impact marker
            folium.Marker(
                [lat, lon],
                popup=f"Impact at {city}",
                tooltip="Impact Point",
                icon=folium.Icon(color="red", icon="star")
            ).add_to(m)

            # Hazard zones
            for z in zones:
                folium.Circle(
                    radius=z["radius"] * 1000,  # km → meters
                    location=[lat, lon],
                    color=z["color"],
                    fill=True,
                    fill_opacity=0.3,
                    popup=z["label"]
                ).add_to(m)

            # Earthquake markers
            if eq_points:
                for e in eq_points:
                    folium.CircleMarker(
                        location=[e["lat"], e["lon"]],
                        radius=max(4, e["mag"] * 2),
                        color="orange",
                        fill=True,
                        fill_opacity=0.7,
                        popup=f"{e['place']} (M {e['mag']})"
                    ).add_to(m)

            # Render map in Streamlit
            st_folium(m, width=900, height=600)

            # Legend + USGS Earthquake Table (same as Globe)
            st.markdown("""
            ### 🧭 How to Read This Map
            - 🟡 **Star marker** → Asteroid impact location  
            - 🔴 **Red zone** → Severe blast and crater area  
            - 🟠 **Orange zone** → Seismic ground shaking area  
            - 🔵 **Blue zone** → Tsunami risk region  
            - 🟠 **Small orange dots** → Real earthquakes from USGS data  
            - 🗺 Use drag + zoom buttons (or enable mouse wheel zoom above).  
            - ⛶ Try Fullscreen for better exploration.  
            """)

            if eq_points:
                st.markdown("#### 🌋 Regional Earthquake Activity (Source: USGS)")
                df_eq = pd.DataFrame(eq_points)[["place", "mag", "lat", "lon"]].rename(
                    columns={"place": "Location", "mag": "Magnitude", "lat": "Latitude", "lon": "Longitude"}
                )
                st.dataframe(df_eq, use_container_width=True)



    # =======================================================
    # TAB 5 — AI INSIGHTS & REPORT (move Gemini + PDF export here)
    # =======================================================
    with tab5:
            # ----------------------------
            # AI Insights
            # ----------------------------
            if st.button("Generate AI Insights"):
                with st.spinner("Thinking..."):
                    original_energy = impact_energy(diameter, velocity) if diameter and velocity else None
                    st.session_state.summary = generate_summary(selected, city, energy, radius, mitigation_method, original_energy)
                    st.session_state.plan = generate_plan(city, radius)
                st.success("AI Insights Generated ✅")

            if "summary" in st.session_state and "plan" in st.session_state:
                st.write("### 🧠 AI Summary")
                st.info(st.session_state.summary)
                st.write("### 🛡 Preparedness Plan")
                st.warning(st.session_state.plan)

                filename = export_pdf(selected, city, energy, radius, st.session_state.summary, st.session_state.plan, mitigation_method, city_data)
                with open(filename, "rb") as f:
                    st.download_button(
                        "📄 Download Impact Report",
                        f,
                        file_name="Impact_Report.pdf",
                        mime="application/pdf",
                    )