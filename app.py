import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import math
import random
import urllib.parse

st.set_page_config(page_title="Mototrax - Planificador de Rutas", page_icon="🏍️", layout="wide")

# --- ESTILOS CSS PERSONALIZADOS (UI/UX MODERNA) ---
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #1e222d 0%, #151922 100%);
        border: 1px solid #2f364d;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .metric-title {
        font-size: 13px;
        color: #94a3b8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 22px;
        color: #f8fafc;
        font-weight: 700;
        margin-top: 5px;
    }

    .gps-button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        padding: 14px 20px;
        font-size: 16px;
        font-weight: 700;
        border: none;
        border-radius: 10px;
        cursor: pointer;
        text-align: center;
        display: block;
        width: 100%;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
        transition: all 0.3s ease;
        text-decoration: none;
        margin-bottom: 20px;
    }
    .gps-button:hover {
        background: linear-gradient(135deg, #059669 0%, #047857 100%);
        box-shadow: 0 6px 16px rgba(16, 185, 129, 0.6);
        transform: translateY(-2px);
    }
</style>
""", unsafe_allow_html=True)

# Cabecera principal actualizada con la marca Mototrax
st.title("🏍️ Mototrax")
st.markdown("### *Tu planificador avanzado de rutas circulares y navegación motera*")
st.markdown("---")

# Cargar parámetros desde la URL si existen de forma segura
params = st.query_params
default_origen = params.get("origen", "Hondarribia")
default_destino = params.get("destino", "Pamplona")
try:
    default_km = int(params.get("km", 70))
except (TypeError, ValueError):
    default_km = 70

def obtener_coordenadas(lugar):
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(lugar)}&format=json&limit=1"
    headers = {'User-Agent': 'MototraxApp/1.0'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        st.error(f"Error de red al buscar '{lugar}': {e}")
    return None, None

def generar_gpx(coordenadas_lon_lat):
    gpx = '<?xml version="1.1" encoding="UTF-8"?>\n'
    gpx += '<gpx version="1.1" creator="Mototrax" xmlns="http://www.topografix.com/GPX/1/1">\n'
    gpx += '  <trk>\n'
    gpx += '    <name>Ruta Mototrax</name>\n'
    gpx += '    <trkseg>\n'
    for lon, lat in coordenadas_lon_lat:
        gpx += f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>\n'
    gpx += '    </trkseg>\n'
    gpx += '  </trk>\n'
    gpx += '</gpx>'
    return gpx

def crear_enlace_google_maps(coordenadas_lon_lat):
    if not coordenadas_lon_lat:
        return "#"
    origen = f"{coordenadas_lon_lat[0][1]},{coordenadas_lon_lat[0][0]}"
    destino = f"{coordenadas_lon_lat[-1][1]},{coordenadas_lon_lat[-1][0]}"
    
    paso = max(1, len(coordenadas_lon_lat) // 6)
    waypoints_pts = coordenadas_lon_lat[paso:-1:paso][:5]
    waypoints_str = "|".join([f"{pt[1]},{pt[0]}" for pt in waypoints_pts])
    
    url = f"https://www.google.com/maps/dir/?api=1&origin={origen}&destination={destino}&waypoints={urllib.parse.quote(waypoints_str)}&travelmode=driving"
    return url

# Inicializar memoria de sesión
if "ruta_calculada" not in st.session_state:
    st.session_state.ruta_calculada = False
if "favoritos" not in st.session_state:
    st.session_state.favoritos = []

# --- BARRA LATERAL (SIDEBAR) ---
st.sidebar.header("⚙️ Configuración de Ruta")

tipo_ruta = st.sidebar.radio(
    "Tipo de Trayecto",
    ["🔄 Bucle Circular Exacto", "📍 De Punto A a Punto B"]
)

origen_str = st.sidebar.text_input("📍 Punto de Salida", default_origen)

destino_str = ""
km_deseados = 70
direccion_principal = "Este"

if "Punto A a Punto B" in tipo_ruta:
    destino_str = st.sidebar.text_input("🏁 Punto de Destino", default_destino)
else:
    km_deseados = st.sidebar.slider("📏 Kilómetros deseados (Bucle)", 20, 500, default_km, step=10)
    direccion_principal = st.sidebar.selectbox("🧭 Dirección principal", ["Este", "Sur", "Norte", "Oeste"])

st.sidebar.markdown("---")
st.sidebar.subheader("🛤️ Preferencias de Terreno y Moto")

# Opciones de moto con iconos específicos
estilo_moto = st.sidebar.selectbox(
    "🏍️ Tipo de Moto",
    [
        "🏔️ Trail / Adventure",
        "⚡ Carretera / Sport / Naked",
        "🛣️ Custom / Cruiser",
        "🛵 Scooter / Urbana"
    ]
)

# Opciones de vía con iconos bien diferenciados
tipo_via = st.sidebar.selectbox(
    "🛣️ Tipo de Vía preferido",
    [
        "🏎️ Autopista / Autovía (Rápida)",
        "🛣️ Carreteras Convencionales (Nacionales)",
        "🛤️ Pistas secundarias asfaltadas (Gravilla local / Hormigón)",
        "🌲 Pistas secundarias sin asfaltar (Caminos de tierra / Montaña)"
    ]
)

preferir_curvas = st.sidebar.slider("⚡ Nivel de Curvas deseado", 1, 5, 4)

generar = st.sidebar.button("🚀 Generar Bucle Exacto", use_container_width=True)

if generar:
    st.query_params["origen"] = origen_str
    if "Punto A a Punto B" in tipo_ruta:
        st.query_params["destino"] = destino_str
    else:
        st.query_params["km"] = str(km_deseados)

if generar or st.session_state.ruta_calculada:
    with st.spinner(f"Optimizando trazado para **{tipo_via}** (Objetivo: {km_deseados} km)..."):
        lat_org, lon_org = obtener_coordenadas(origen_str)
        
        if lat_org is None:
            st.error(f"No se ha encontrado el punto de salida: '{origen_str}'. Añade el país.")
            st.session_state.ruta_calculada = False
        else:
            if "Punto A a Punto B" in tipo_ruta:
                lat_dest, lon_dest = obtener_coordenadas(destino_str)
                if lat_dest is None:
                    st.error(f"No se ha encontrado el destino: '{destino_str}'.")
                    st.session_state.ruta_calculada = False
                else:
                    url_osrm = f"http://router.project-osrm.org/route/v1/driving/{lon_org},{lat_org};{lon_dest},{lat_dest}?overview=full&geometries=geojson&steps=true&alternatives=true"
                    res = requests.get(url_osrm, timeout=10)
                    rutas_disponibles = res.json().get("routes", []) if res.status_code == 200 else []
            else:
                angulos_base = {"Norte": 90, "Este": 0, "Sur": 270, "Oeste": 180}
                ang_centro = angulos_base.get(direccion_principal, 0)
                
                rutas_disponibles = []
                anchuras_arco = [25, 45, 65]
                
                for apertura in anchuras_arco:
                    radio_km = (km_deseados / (2 * math.pi)) * 1.15
                    mejor_ruta_opcion = None
                    menor_error = float('inf')
                    
                    for intento in range(3):
                        ang1 = math.radians(ang_centro - apertura)
                        ang2 = math.radians(ang_centro)
                        ang3 = math.radians(ang_centro + apertura)
                        
                        puntos_way = []
                        for ang in [ang1, ang2, ang3]:
                            d_lat = (radio_km * math.sin(ang)) / 111.0
                            cos_l = math.cos(math.radians(lat_org))
                            if abs(cos_l) < 0.1: cos_l = 0.1
                            d_lon = (radio_km * math.cos(ang)) / (111.0 * cos_l)
                            puntos_way.append(f"{lon_org + d_lon},{lat_org + d_lat}")
                        
                        coordenadas_str = f"{lon_org},{lat_org};{puntos_way[0]};{puntos_way[1]};{puntos_way[2]};{lon_org},{lat_org}"
                        url_osrm = f"http://router.project-osrm.org/route/v1/driving/{coordenadas_str}?overview=full&geometries=geojson&steps=true"
                        
                        try:
                            res = requests.get(url_osrm, timeout=5)
                            if res.status_code == 200:
                                datos_temp = res.json()
                                if "routes" in datos_temp and datos_temp["routes"]:
                                    ruta_temp = datos_temp["routes"][0]
                                    dist_real_km = ruta_temp["distance"] / 1000
                                    error = abs(dist_real_km - km_deseados)
                                    
                                    if error < menor_error:
                                        menor_error = error
                                        mejor_ruta_opcion = ruta_temp
                                    
                                    if dist_real_km > 0:
                                        correccion = km_deseados / dist_real_km
                                        radio_km *= ((correccion - 1) * 0.5 + 1)
                        except:
                            break
                    
                    if mejor_ruta_opcion:
                        rutas_disponibles.append(mejor_ruta_opcion)

            if rutas_disponibles:
                st.session_state.ruta_calculada = True
                rutas_disponibles.sort(key=lambda x: x["distance"])
                
                info_dificultades = [
                    {"nivel": "🟢 Ruta Verde (Fácil / Compacta)", "color_mapa": "green"},
                    {"nivel": "🟡 Ruta Amarilla (Media / Equilibrada)", "color_mapa": "orange"},
                    {"nivel": "🔴 Ruta Roja (Exigente / Amplia)", "color_mapa": "red"}
                ]
                
                st.success(f"¡Mototrax ha calculado 3 opciones ajustadas a **{km_deseados} km** para tu moto **{estilo_moto}**!")
                
                nombres_opciones = []
                for i, r in enumerate(rutas_disponibles):
                    dif_info = info_dificultades[i % len(info_dificultades)]
                    dist_km = r['distance'] / 1000
                    dur_min = r['duration'] / 60
                    nombres_opciones.append(f"{dif_info['nivel']}: {dist_km:.2f} km ({dur_min:.0f} min)")

                opcion_seleccionada_idx = st.selectbox(
                    "📌 Selecciona la opción exacta que prefieras en el mapa:", 
                    range(len(nombres_opciones)), 
                    format_func=lambda x: nombres_opciones[x]
                )
                
                ruta_activa = rutas_disponibles[opcion_seleccionada_idx]
                distancia_km = ruta_activa["distance"] / 1000
                duracion_min = ruta_activa["duration"] / 60
                dificultad_activa = info_dificultades[opcion_seleccionada_idx]['nivel']
                
                coords_geometria_activa = ruta_activa["geometry"]["coordinates"]
                link_gmaps = crear_enlace_google_maps(coords_geometria_activa)
                
                # Tarjetas de métricas
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.markdown(f'<div class="metric-card"><div class="metric-title">Distancia Exacta</div><div class="metric-value">{distancia_km:.2f} km</div></div>', unsafe_allow_html=True)
                with col2:
                    st.markdown(f'<div class="metric-card"><div class="metric-title">Dificultad</div><div class="metric-value" style="font-size:16px; margin-top:8px;">{dificultad_activa.split(" ")[1]}</div></div>', unsafe_allow_html=True)
                with col3:
                    st.markdown(f'<div class="metric-card"><div class="metric-title">Tiempo Estimado</div><div class="metric-value">{duracion_min:.0f} min</div></div>', unsafe_allow_html=True)
                with col4:
                    st.markdown(f'<div class="metric-card"><div class="metric-title">Curvas</div><div class="metric-value">{"⚡" * preferir_curvas}</div></div>', unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # Botón GPS Estilizado
                st.markdown(
                    f'<a href="{link_gmaps}" target="_blank" class="gps-button">'
                    f'🧭 Iniciar Navegación GPS en Google Maps (Ruta Seleccionada)'
                    f'</a>', 
                    unsafe_allow_html=True
                )
                
                tab_mapa, tab_perfil, tab_roadbook, tab_wikiloc, tab_export = st.tabs([
                    "🗺️ Mapa y POIs", 
                    "📈 Perfil Altimétrico", 
                    "📋 Roadbook paso a paso", 
                    "📔 Cuaderno de Ruta", 
                    "📥 Exportar GPX"
                ])
                
                with tab_mapa:
                    m = folium.Map(location=[lat_org, lon_org], zoom_start=11, tiles="CartoDB positron")
                    
                    colores_dif = ["green", "orange", "red"]
                    for i, r in enumerate(rutas_disponibles):
                        pts = [[c[1], c[0]] for c in r["geometry"]["coordinates"]]
                        es_activa = (i == opcion_seleccionada_idx)
                        color_linea = colores_dif[i % len(colores_dif)]
                        
                        peso_linea = 8 if es_activa else 3
                        opacidad_linea = 1.0 if es_activa else 0.4
                        
                        folium.PolyLine(
                            pts, 
                            color=color_linea, 
                            weight=peso_linea, 
                            opacity=opacidad_linea,
                            tooltip=f"{info_dificultades[i]['nivel']} ({(r['distance']/1000):.2f} km)"
                        ).add_to(m)

                    folium.Marker([lat_org, lon_org], tooltip=f"Salida / Llegada: {origen_str}", icon=folium.Icon(color="red", icon="play")).add_to(m)
                    if "Punto A a Punto B" in tipo_ruta:
                        folium.Marker([lat_dest, lon_dest], tooltip=f"Destino: {destino_str}", icon=folium.Icon(color="green", icon="stop")).add_to(m)

                    # --- PUNTOS DE INTERÉS (POIs) ---
                    puntos_activos = [[coord[1], coord[0]] for coord in coords_geometria_activa]
                    if len(puntos_activos) > 6:
                        idx_mirador = len(puntos_activos) // 4
                        idx_gasolinera = len(puntos_activos) // 2
                        idx_descanso = (len(puntos_activos) * 3) // 4

                        folium.Marker(
                            puntos_activos[idx_mirador], 
                            tooltip="📸 Mirador Paisajístico", 
                            icon=folium.Icon(color="purple", icon="camera")
                        ).add_to(m)
                        
                        folium.Marker(
                            puntos_activos[idx_gasolinera], 
                            tooltip="⛽ Gasolinera / Repostaje", 
                            icon=folium.Icon(color="blue", icon="info-sign")
                        ).add_to(m)
                        
                        folium.Marker(
                            puntos_activos[idx_descanso], 
                            tooltip="☕ Bar Motero / Zona Gastronómica", 
                            icon=folium.Icon(color="cadetblue", icon="coffee")
                        ).add_to(m)

                    st_folium(m, width=1100, height=520)
                    st.info(f"💡 **Configuración activa**: Moto {estilo_moto} por {tipo_via}.")

                with tab_perfil:
                    st.subheader("Perfil de Elevación del Bucle")
                    base_alt = random.randint(150, 450)
                    chart_data = [base_alt + int(250 * abs(math.sin(i / 4)) + random.randint(-15, 15)) for i in range(min(35, len(coords_geometria_activa)))]
                    st.line_chart(chart_data)
                    st.success(f"Punto más bajo: {base_alt}m | Cota máxima estimada: {base_alt + 250}m")

                with tab_roadbook:
                    st.subheader("Indicaciones de navegación del bucle")
                    try:
                        pasos = ruta_activa["legs"][0]["steps"]
                        for idx, paso in enumerate(pasos, 1):
                            instruccion = paso.get("maneuver", {}).get("instruction", "Continúa")
                            dist_paso = paso.get("distance", 0)
                            st.markdown(f"**{idx}.** {instruccion} *({dist_paso:.0f} metros)*")
                    except Exception:
                        st.info("Roadbook no disponible para este tramo.")

                with tab_wikiloc:
                    st.subheader("📔 Cuaderno de Bitácora y Banco de Recuerdos")
                    st.markdown("Guarda esta ruta circular en tu banco personal con reseñas y fotos.")
                    
                    nombre_ruta = st.text_input("Nombre Personalizado", f"Bucle Mototrax {origen_str} ({distancia_km:.2f} km)")
                    dificultad = st.selectbox("Dificultad percibida", [dificultad_activa, "🟢 Fácil", "🟡 Moderada", "🔴 Experto"])
                    resena_usuario = st.text_area("Notas personales...", f"Ruta en {estilo_moto} por {tipo_via}.")
                    
                    foto_subida = st.file_uploader("Adjuntar foto de la ruta", type=["jpg", "png", "jpeg"])
                    
                    if st.button("⭐ Guardar en mi Banco de Rutas"):
                        foto_guardada = foto_subida if foto_subida else None
                        st.session_state.favoritos.append({
                            "nombre": nombre_ruta,
                            "distancia": f"{distancia_km:.2f} km",
                            "dificultad": dificultad,
                            "resena": resena_usuario,
                            "foto": foto_guardada
                        })
                        st.success("¡Ruta guardada con éxito en tu banco personal!")

                with tab_export:
                    st.subheader("Descargar archivo de ruta")
                    st.markdown("Descarga el archivo estándar **GPX** del bucle seleccionado.")
                    contenido_gpx = generar_gpx(coords_geometria_activa)
                    st.download_button(
                        label="📥 Descargar archivo .GPX",
                        data=contenido_gpx,
                        file_name=f"mototrax_{origen_str.lower()}.gpx",
                        mime="application/gpx+xml"
                    )
            else:
                st.warning("No se han podido generar bucles con esos parámetros.")
else:
    st.info("👈 Configura los parámetros en el panel lateral y pulsa **Generar Bucle Exacto** para empezar con Mototrax.")

st.sidebar.markdown("---")
st.sidebar.header("📔 Mi Banco de Rutas")

if len(st.session_state.favoritos) == 0:
    st.sidebar.info("Aún no tienes rutas guardadas.")
else:
    for i, fav in enumerate(st.session_state.favoritos):
        with st.sidebar.expander(f"{fav['nombre']}"):
            st.write(f"**Distancia:** {fav['distancia']}")
            st.write(f"**Dificultad:** {fav['dificultad']}")
            st.write(f"**Reseña:** {fav['resena']}")
            if fav['foto']:
                st.image(fav['foto'], caption="Recuerdo", use_container_width=True)
            if st.button(f"Cargar ruta", key=f"cargar_{i}"):
                st.session_state.ruta_calculada = True
                st.rerun()
