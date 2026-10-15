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
    st.markdown("*Automatisierte Grundriss-Auswertung (EG & DG) und Rohrnetz-Dimensionierung*")
    st.markdown("Ersetzt keine Heizlastberechnung nach Norm 12831")

st.markdown("---")

# ==========================================
# FUSSBODENHEIZUNG & ETAGEN-PLANUNG
# ==========================================
st.subheader("📐 Automatische Grundriss-Auswertung nach Etagen (EG & DG)")
st.markdown("Laden Sie Ihren Plan als PDF hoch. Die App trennt die Räume automatisch in Erdgeschoss (EG) und Dachgeschoss (DG) und erlaubt die manuelle Nachbearbeitung.")

uploaded_file = st.file_uploader("Grundriss hochladen (PDF)", type=["pdf"], key="pdf_upload_etagen")

eg_rooms = []
dg_rooms = []

if uploaded_file is not None:
    try:
        reader = pypdf.PdfReader(uploaded_file)
        for page in reader.pages:
            text = page.extract_text()
            lines = text.split('\n')
            is_dg = False
            for i, line in enumerate(lines):
                if "Kind 1" in line or "Dachschräge" in line:
                    is_dg = True

                if "F:" in line and "m" in line:
                    match = re.search(r"F:\s*([0-9.,]+)", line)
                    if match:
                        area_str = match.group(1).replace(',', '.')
                        try:
                            area = float(area_str)
                            room_name = lines[i-1].strip() if i > 0 else "Raum"
                            va = 10 if "Bad" in room_name else 15
                            kreise = max(1, round(area / 18))
                            
                            room_data = {
                                "Raumbezeichnung": room_name,
                                "Fläche [m²]": area,
                                "Verlegeabstand [cm]": va,
                                "Heizkreise": kreise
                            }
                            
                            if room_name in ["Kind 1", "Kind 2", "Schlafen", "Büro"] or (is_dg and room_name in ["Flur", "Bad"]):
                                dg_rooms.append(room_data)
                            else:
                                eg_rooms.append(room_data)
                        except ValueError:
                            pass
        if eg_rooms or dg_rooms:
            st.success("Plan erfolgreich nach Etagen (EG & DG) ausgelesen!")
    except Exception as e:
        st.error(f"Fehler beim Lesen der PDF: {e}")

if not eg_rooms and not dg_rooms:
    eg_rooms = [
        {"Raumbezeichnung": "Wohnen / Essen / Kochen", "Fläche [m²]": 83.29, "Verlegeabstand [cm]": 15, "Heizkreise": 5},
        {"Raumbezeichnung": "Diele", "Fläche [m²]": 12.11, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
        {"Raumbezeichnung": "HWR", "Fläche [m²]": 7.25, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
        {"Raumbezeichnung": "Technik", "Fläche [m²]": 6.75, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
        {"Raumbezeichnung": "WC", "Fläche [m²]": 2.55, "Verlegeabstand [cm]": 10, "Heizkreise": 1},
        {"Raumbezeichnung": "Lager", "Fläche [m²]": 5.09, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
    ]
    dg_rooms = [
        {"Raumbezeichnung": "Kind 1", "Fläche [m²]": 17.91, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
        {"Raumbezeichnung": "Kind 2", "Fläche [m²]": 17.90, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
        {"Raumbezeichnung": "Schlafen", "Fläche [m²]": 16.08, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
        {"Raumbezeichnung": "Büro", "Fläche [m²]": 30.43, "Verlegeabstand [cm]": 15, "Heizkreise": 2},
        {"Raumbezeichnung": "Bad", "Fläche [m²]": 9.66, "Verlegeabstand [cm]": 10, "Heizkreise": 1},
        {"Raumbezeichnung": "Flur", "Fläche [m²]": 5.89, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
    ]

st.markdown("### 🏠 Erdgeschoss (EG)")
df_eg = pd.DataFrame(eg_rooms)
edited_eg = st.data_editor(df_eg, num_rows="dynamic", use_container_width=True, key="editor_eg")

st.markdown("### 🏠 Dachgeschoss (DG)")
df_dg = pd.DataFrame(dg_rooms)
edited_dg = st.data_editor(df_dg, num_rows="dynamic", use_container_width=True, key="editor_dg")

gesamt_flaeche = (edited_eg["Fläche [m²]"].sum() if not edited_eg.empty else 0) + (edited_dg["Fläche [m²]"].sum() if not edited_dg.empty else 0)
gesamt_kreise = (int(edited_eg["Heizkreise"].sum()) if not edited_eg.empty else 0) + (int(edited_dg["Heizkreise"].sum()) if not edited_dg.empty else 0)

rohrbedarf_gesamt = 0
for df_etage in [edited_eg, edited_dg]:
    if not df_etage.empty:
        for _, row in df_etage.iterrows():
            va = row["Verlegeabstand [cm]"]
            fl = row["Fläche [m²]"]
            if va > 0:
                faktor = 100.0 / va + 1.5
                rohrbedarf_gesamt += fl * faktor

st.markdown("---")
st.subheader("📈 Gesamt-Auswertung über alle Etagen")
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    st.metric(label="Gesamt-Beheizte Fläche", value=f"{gesamt_flaeche:.2f} m²")
with col_f2:
    st.metric(label="Anzahl Heizkreise gesamt", value=f"{gesamt_kreise} Kreise")
with col_f3:
    st.metric(label="Geschätzter Rohrbedarf gesamt", value=f"{rohrbedarf_gesamt:.0f} Meter")
