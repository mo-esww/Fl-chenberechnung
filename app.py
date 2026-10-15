import streamlit as st
import pandas as pd
import numpy as np
import pypdf
import re

# --- Seiten-Konfiguration & Corporate Design ---
st.set_page_config(
    page_title="Fußbodenheizungs-Planer per Grundriss-Upload", 
    page_icon="📐", 
    layout="wide"
)

# Eigene CSS-Anpassungen mit dem Farbcode #4bb6c4
st.markdown("""
    <style>
    .main {
        background-color: #f9f9f9;
    }
    h1 {
        color: #111111;
    }
    h2, h3 {
        color: #4bb6c4 !important;
    }
    .stButton>button {
        background-color: #4bb6c4;
        color: white;
        border-radius: 5px;
        width: 100%;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #3aa2af;
        color: white;
    }
    [data-testid="stMetricValue"] {
        color: #4bb6c4;
    }
    </style>
""", unsafe_allow_html=True)

# --- Kopfbereich mit Logo und Titel ---
col_logo, col_title = st.columns([1, 3])
with col_logo:
    st.image("https://www.es-ww.de/wp-content/uploads/2023/02/Logo_ESW_farbig-2048x546.png", width=280)

with col_title:
    st.title("Fußbodenheizungs-Planer nach Etagen")
    st.markdown("*Automatisierte Grundriss-Auswertung (Multi-Upload) und Rohrnetz-Dimensionierung*")
    st.markdown("Ersetzt keine Heizlastberechnung nach Norm 12831")

st.markdown("---")

# ==========================================
# FUSSBODENHEIZUNG & ETAGEN-PLANUNG
# ==========================================
st.subheader("📐 Automatische Grundriss-Auswertung (Multi-Upload)")
st.markdown("Laden Sie hier eine oder **mehrere** Plan-PDFs hoch.")

# Multi-Upload Feld
uploaded_files = st.file_uploader("Grundrisse hochladen (PDF)", type=["pdf"], accept_multiple_files=True, key="pdf_upload_etagen")

# Prüfen, ob sich die hochgeladenen Dateien geändert haben
uploaded_files_names = [f.name for f in uploaded_files] if uploaded_files else []
if "last_uploaded_files" not in st.session_state:
    st.session_state.last_uploaded_files = []

if uploaded_files_names != st.session_state.last_uploaded_files:
    st.session_state.last_uploaded_files = uploaded_files_names
    if "df_eg" in st.session_state:
        del st.session_state.df_eg
    if "df_dg" in st.session_state:
        del st.session_state.df_dg

eg_rooms = []
dg_rooms = []

if uploaded_files:
    try:
        for uploaded_file in uploaded_files:
            reader = pypdf.PdfReader(uploaded_file)
            for page in reader.pages:
                text = page.extract_text()
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                is_dg = False
                
                for i, line in enumerate(lines):
                    # Etagen-Erkennung anhand Dateinamen oder Textmarken
                    if "DG" in uploaded_file.name.upper() or "DACH" in uploaded_file.name.upper() or "Kind 1" in line or "Dachschräge" in line:
                        is_dg = True

                    area = None
                    room_name = "Raum"

                    # Format 1: "XX.XX m²" (z.B. aus dem neuen Plan)
                    if "m²" in line or "m 2" in line:
                        match = re.search(r'([0-9.,]+)\s*m[²2]', line)
                        if match:
                            try:
                                area = float(match.group(1).replace(',', '.'))
                                room_name = lines[i-1] if i > 0 else "Raum"
                            except ValueError:
                                pass

                    # Format 2: "F: XX.XX m 2" (aus dem alten Vorabzug-Plan)
                    elif "F:" in line:
                        match = re.search(r"F:\s*([0-9.,]+)", line)
                        if match:
                            try:
                                area = float(match.group(1).replace(',', '.'))
                                room_name = lines[i-1] if i > 0 else "Raum"
                            except ValueError:
                                pass

                    if area is not None and area < 500: # Filter gegen falsche Treffer (z.B. Maßketten)
                        # Unwichtige Systemzeilen ausschließen
                        if "Allplan" in room_name or "Beetzendorf" in room_name or "Blatt" in room_name:
                            continue

                        va = 10 if "Bad" in room_name.lower() else 15
                        kreise = max(1, round(area / 18))
                        
                        room_data = {
                            "Raumbezeichnung": room_name,
                            "Fläche [m²]": area,
                            "Verlegeabstand [cm]": va,
                            "Heizkreise": kreise
                        }
                        
                        # Zuordnung zu EG oder DG
                        if is_dg or room_name in ["Kind 1", "Kind 2", "Schlafen", "Büro"]:
                            dg_rooms.append(room_data)
                        else:
                            eg_rooms.append(room_data)

        if eg_rooms or dg_rooms:
            st.success(f"Erfolgreich {len(uploaded_files)} Datei(en) eingelesen und Räume extrahiert!")
    except Exception as e:
        st.error(f"Fehler beim Lesen der PDFs: {e}")

# Fallback oder Initialisierung
if not eg_rooms and not dg_rooms and not uploaded_files:
    eg_rooms = [
        {"Raumbezeichnung": "Wohnen / Essen / Kochen", "Fläche [m²]": 55.04, "Verlegeabstand [cm]": 15, "Heizkreise": 3},
        {"Raumbezeichnung": "Küche", "Fläche [m²]": 17.81, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
        {"Raumbezeichnung": "Diele", "Fläche [m²]": 13.50, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
        {"Raumbezeichnung": "Duschbad", "Fläche [m²]": 5.70, "Verlegeabstand [cm]": 10, "Heizkreise": 1},
    ]
    dg_rooms = [
        {"Raumbezeichnung": "Schlafen", "Fläche [m²]": 16.08, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
        {"Raumbezeichnung": "Bad", "Fläche [m²]": 9.66, "Verlegeabstand [cm]": 10, "Heizkreise": 1},
    ]

# --- Erdgeschoss ---
st.markdown("### 🏠 Erdgeschoss (EG)")
if "df_eg" not in st.session_state or uploaded_files:
    st.session_state.df_eg = pd.DataFrame(eg_rooms)

edited_eg = st.data_editor(st.session_state.df_eg, num_rows="dynamic", use_container_width=True, key="editor_eg")
st.session_state.df_eg = edited_eg

eg_flaeche = edited_eg["Fläche [m²]"].sum() if not edited_eg.empty else 0
eg_kreise = int(edited_eg["Heizkreise"].sum()) if not edited_eg.empty else 0
eg_rohr = sum([fl * (100.0 / va + 1.5) for _, row in edited_eg.iterrows() for va, fl in [(row["Verlegeabstand [cm]"], row["Fläche [m²]"])] if va > 0]) if not edited_eg.empty else 0

col_e1, col_e2, col_e3 = st.columns(3)
with col_e1:
    st.metric(label="Fläche EG", value=f"{eg_flaeche:.2f} m²")
with col_e2:
    st.metric(label="Heizkreise EG (Verteiler)", value=f"{eg_kreise} Kreise")
with col_e3:
    st.metric(label="Rohrbedarf EG", value=f"{eg_rohr:.0f} Meter")

st.markdown("---")

# --- Dachgeschoss ---
st.markdown("### 🏠 Dachgeschoss / Obergeschoss (DG)")
if "df_dg" not in st.session_state or uploaded_files:
    st.session_state.df_dg = pd.DataFrame(dg_rooms)

edited_dg = st.data_editor(st.session_state.df_dg, num_rows="dynamic", use_container_width=True, key="editor_dg")
st.session_state.df_dg = edited_dg

dg_flaeche = edited_dg["Fläche [m²]"].sum() if not edited_dg.empty else 0
dg_kreise = int(edited_dg["Heizkreise"].sum()) if not edited_dg.empty else 0
dg_rohr = sum([fl * (100.0 / va + 1.5) for _, row in edited_dg.iterrows() for va, fl in [(row["Verlegeabstand [cm]"], row["Fläche [m²]"])] if va > 0]) if not edited_dg.empty else 0

col_d1, col_d2, col_d3 = st.columns(3)
with col_d1:
    st.metric(label="Fläche DG", value=f"{dg_flaeche:.2f} m²")
with col_d2:
    st.metric(label="Heizkreise DG (Verteiler)", value=f"{dg_kreise} Kreise")
with col_d3:
    st.metric(label="Rohrbedarf DG", value=f"{dg_rohr:.0f} Meter")

# --- Summiertes Gesamtergebnis ---
gesamt_flaeche = eg_flaeche + dg_flaeche
rohrbedarf_gesamt = eg_rohr + dg_rohr

st.markdown("---")
st.subheader("📈 Summiertes Gesamtergebnis (Gesamtgebäude)")
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    st.metric(label="Gesamt-Beheizte Fläche", value=f"{gesamt_flaeche:.2f} m²")
with col_f2:
    st.metric(label="Heizkreise getrennt", value=f"EG: {eg_kreise} | DG: {dg_kreise}")
with col_f3:
    st.metric(label="Gesamter Rohrbedarf", value=f"{rohrbedarf_gesamt:.0f} Meter")
