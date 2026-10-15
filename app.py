import streamlit as st
import pandas as pd
import numpy as np
import pypdf
import re

# --- Seiten-Konfiguration & Corporate Design ---
st.set_page_config(
    page_title="Fußbodenheizungs-Planer nach Etagen", 
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
    st.title("Fußbodenheizungs-Planer für Wohngebäude")
    st.markdown("*Automatisierte Grundriss-Auswertung & Etagen-Zuweisung (UG, EG, OG, DG)*")
    st.markdown("Ersetzt keine Heizlastberechnung nach Norm 12831")

st.markdown("---")

# ==========================================
# FUSSBODENHEIZUNG & MEHR-ETAGEN-PLANUNG
# ==========================================
st.subheader("📐 Grundriss-Auswertung über mehrere Geschosse")
st.markdown("Laden Sie Ihre Plan-PDFs hoch. Die App liest die Räume aus und teilt sie den Etagen zu. Sie können die Tabellen unten jederzeit manuell ergänzen oder anpassen.")

uploaded_files = st.file_uploader("Grundrisse hochladen (PDF)", type=["pdf"], accept_multiple_files=True, key="pdf_upload_multi")

etagen_definitionen = {
    "UG": "Untergeschoss / Keller",
    "EG": "Erdgeschoss",
    "OG": "Obergeschoss",
    "DG": "Dachgeschoss"
}

# Initialisierung der Session States
if "etagen_daten" not in st.session_state or uploaded_files:
    temp_etagen = {k: [] for k in etagen_definitionen.keys()}
    
    # Standard-Fallback
    temp_etagen["EG"] = [
        {"Raumbezeichnung": "Essen/Wohnen", "Fläche [m²]": 55.04, "Verlegeabstand [cm]": 15, "Heizkreise": 3},
        {"Raumbezeichnung": "Küche", "Fläche [m²]": 17.81, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
        {"Raumbezeichnung": "Diele", "Fläche [m²]": 13.50, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
        {"Raumbezeichnung": "Duschbad", "Fläche [m²]": 5.70, "Verlegeabstand [cm]": 10, "Heizkreise": 1},
    ]

    if uploaded_files:
        try:
            for uploaded_file in uploaded_files:
                filename_upper = uploaded_file.name.upper()
                ziel_etage = "EG"
                for etage_key in etagen_definitionen.keys():
                    if etage_key in filename_upper:
                        ziel_etage = etage_key

                reader = pypdf.PdfReader(uploaded_file)
                for page in reader.pages:
                    text = page.extract_text()
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    
                    for i, line in enumerate(lines):
                        area = None
                        room_name = ""

                        # Verbesserte Erkennung für verschiedene Flächenformate (z.B. "55.04 m²", "F: 12.11 m 2")
                        if "m²" in line or "m 2" in line or "F:" in line:
                            match = re.search(r'([0-9.,]+)\s*(?:m[²2]|m\s*2)', line)
                            if not match and "F:" in line:
                                match = re.search(r"F:\s*([0-9.,]+)", line)
                                
                            if match:
                                try:
                                    val_str = match.group(1).replace(',', '.')
                                    area = float(val_str)
                                    # Suche in der direkten Umgebung nach dem RaumNamen
                                    if i > 0:
                                        room_name = lines[i-1]
                                    if not room_name or len(room_name) < 2 or any(char.isdigit() for char in room_name):
                                        if i > 1:
                                            room_name = lines[i-2]
                                except ValueError:
                                    pass

                        if area is not None and 1.0 < area < 400: # Realistischer Flächenbereich für Räume
                            # Unwichtige Systemtexte filtern
                            if any(x in room_name for x in ["Allplan", "Beetzendorf", "Blatt", "Architekt", "Stg", "Mauer"]):
                                continue
                            if not room_name:
                                room_name = "Raum (unbenannt)"

                            va = 10 if "bad" in room_name.lower() or "wc" in room_name.lower() else 15
                            kreise = max(1, round(area / 18))
                            
                            # Vermeide Doppeleinträge derselben Fläche
                            existing_areas = [r["Fläche [m²]"] for r in temp_etagen[ziel_etage]]
                            if area not in existing_areas:
                                temp_etagen[ziel_etage].append({
                                    "Raumbezeichnung": room_name,
                                    "Fläche [m²]": area,
                                    "Verlegeabstand [cm]": va,
                                    "Heizkreise": kreise
                                })
            
            st.session_state.etagen_daten = temp_etagen
            st.success("Pläne erfolgreich eingelesen! Sie können fehlende Räume in den Tabellen unten auch direkt per Hand hinzufügen.")
        except Exception as e:
            st.error(f"Fehler beim Auslesen der Dateien: {e}")

# --- Dynamische Anzeige und Editierung für jede Etage ---
etagen_ergebnisse = {}

for etage_key, etage_titel in etagen_definitionen.items():
    st.markdown(f"### 🏢 {etage_titel} ({etage_key})")
    
    df_etage = pd.DataFrame(st.session_state.etagen_daten[etage_key])
    
    # Interaktiver Editor (hier kannst du ganz einfach Zeilen hinzufügen oder korrigieren)
    edited_df = st.data_editor(df_etage, num_rows="dynamic", use_container_width=True, key=f"editor_{etage_key}")
    st.session_state.etagen_daten[etage_key] = edited_df.to_dict('records')
    
    e_flaeche = edited_df["Fläche [m²]"].sum() if not edited_df.empty else 0
    e_kreise = int(edited_df["Heizkreise"].sum()) if not edited_df.empty else 0
    e_rohr = sum([fl * (100.0 / va + 1.5) for _, row in edited_df.iterrows() for va, fl in [(row["Verlegeabstand [cm]"], row["Fläche [m²]"])] if va > 0]) if not edited_df.empty else 0
    
    etagen_ergebnisse[etage_key] = {"flaeche": e_flaeche, "kreise": e_kreise, "rohr": e_rohr}
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label=f"Fläche {etage_key}", value=f"{e_flaeche:.2f} m²")
    with col2:
        st.metric(label=f"Heizkreise {etage_key} (Verteiler)", value=f"{e_kreise} Kreise")
    with col3:
        st.metric(label=f"Rohrbedarf {etage_key}", value=f"{e_rohr:.0f} Meter")
        
    st.markdown("---")

# --- Summiertes Gesamtergebnis ---
total_flaeche = sum([res["flaeche"] for res in etagen_ergebnisse.values()])
total_rohr = sum([res["rohr"] for res in etagen_ergebnisse.values()])
kreise_str = " | ".join([f"{k}: {res['kreise']}" for k, res in etagen_ergebnisse.items() if res['kreise'] > 0])

st.subheader("📈 Summiertes Gesamtergebnis (Gesamtgebäude)")
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    st.metric(label="Gesamt-Beheizte Fläche", value=f"{total_flaeche:.2f} m²")
with col_f2:
    st.metric(label="Heizkreise je Verteiler", value=kreise_str if kreise_str else "0 Kreise")
with col_f3:
    st.metric(label="Gesamter Rohrbedarf", value=f"{total_rohr:.0f} Meter")
