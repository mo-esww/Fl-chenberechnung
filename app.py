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
    st.title("Fußbodenheizungs-Planer für Mehrfamilien- & Wohngebäude")
    st.markdown("*Automatisierte Grundriss-Auswertung für beliebig viele Etagen (UG, EG, OG, DG)*")
    st.markdown("Ersetzt keine Heizlastberechnung nach Norm 12831")

st.markdown("---")

# ==========================================
# FUSSBODENHEIZUNG & MEHR-ETAGEN-PLANUNG
# ==========================================
st.subheader("📐 Grundriss-Auswertung über mehrere Geschosse")
st.markdown("Laden Sie Ihre Plan-PDFs hoch. Die App erkennt oder verteilt die Räume automatisch auf die Etagen (UG, EG, OG, DG).")

uploaded_files = st.file_uploader("Grundrisse hochladen (PDF)", type=["pdf"], accept_multiple_files=True, key="pdf_upload_multi")

# Etagen-Struktur definieren
etagen_definitionen = {
    "UG": "Untergeschoss / Keller",
    "EG": "Erdgeschoss",
    "OG": "Obergeschoss",
    "DG": "Dachgeschoss"
}

# Initialisierung der Session States für jede Etage
if "etagen_daten" not in st.session_state or uploaded_files:
    # Standard-Fallbacks falls noch keine Pläne hochgeladen wurden
    st.session_state.etagen_daten = {
        "UG": [{"Raumbezeichnung": "Keller / Technik", "Fläche [m²]": 20.0, "Verlegeabstand [cm]": 20, "Heizkreise": 1}],
        "EG": [
            {"Raumbezeichnung": "Essen/Wohnen", "Fläche [m²]": 55.04, "Verlegeabstand [cm]": 15, "Heizkreise": 3},
            {"Raumbezeichnung": "Küche", "Fläche [m²]": 17.81, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
            {"Raumbezeichnung": "Diele", "Fläche [m²]": 13.50, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
            {"Raumbezeichnung": "Duschbad", "Fläche [m²]": 5.70, "Verlegeabstand [cm]": 10, "Heizkreise": 1},
        ],
        "OG": [
            {"Raumbezeichnung": "Schlafen", "Fläche [m²]": 20.0, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
            {"Raumbezeichnung": "Kind 1", "Fläche [m²]": 16.0, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
        ],
        "DG": [
            {"Raumbezeichnung": "Studio / Dachboden", "Fläche [m²]": 25.0, "Verlegeabstand [cm]": 15, "Heizkreise": 1}
        ]
    }

    if uploaded_files:
        # Etagen leeren und neu füllen durch Auslesen
        temp_etagen = {k: [] for k in etagen_definitionen.keys()}
        try:
            for uploaded_file in uploaded_files:
                filename_upper = uploaded_file.name.upper()
                # Bestimme Ziel-Etage anhand des Dateinamens falls möglich, sonst Standard EG
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
                        room_name = "Raum"

                        if "m²" in line or "m 2" in line:
                            match = re.search(r'([0-9.,]+)\s*m[²2]', line)
                            if match:
                                try:
                                    area = float(match.group(1).replace(',', '.'))
                                    room_name = lines[i-1] if i > 0 else "Raum"
                                except ValueError:
                                    pass
                        elif "F:" in line:
                            match = re.search(r"F:\s*([0-9.,]+)", line)
                            if match:
                                try:
                                    area = float(match.group(1).replace(',', '.'))
                                    room_name = lines[i-1] if i > 0 else "Raum"
                                except ValueError:
                                    pass

                        if area is not None and area < 500:
                            if any(x in room_name for x in ["Allplan", "Beetzendorf", "Blatt", "Architekt"]):
                                continue
                            va = 10 if "Bad" in room_name.lower() or "Duschbad" in room_name.lower() else 15
                            kreise = max(1, round(area / 18))
                            
                            temp_etagen[ziel_etage].append({
                                "Raumbezeichnung": room_name,
                                "Fläche [m²]": area,
                                "Verlegeabstand [cm]": va,
                                "Heizkreise": kreise
                            })
            
            # Übernahme falls Räume gefunden wurden
            if any(temp_etagen.values()):
                st.session_state.etagen_daten = temp_etagen
                st.success("Pläne erfolgreich analysiert und auf die Geschosse aufgeteilt!")
        except Exception as e:
            st.error(f"Fehler beim Auslesen der Dateien: {e}")

# --- Dynamische Anzeige und Editierung für jede Etage ---
gesamt_flaeche = 0
gesamt_rohr = ohne_summe_kreise = {}
etagen_ergebnisse = {}

for etage_key, etage_titel in etagen_definitionen.items():
    st.markdown(f"### 🏢 {etage_titel} ({etage_key})")
    
    # DataFrame aus Session State holen
    df_etage = pd.DataFrame(st.session_state.etagen_daten[etage_key])
    
    # Editor für diese Etage
    edited_df = st.data_editor(df_etage, num_rows="dynamic", use_container_width=True, key=f"editor_{etage_key}")
    st.session_state.etagen_daten[etage_key] = edited_df.to_dict('records')
    
    # Berechnungen pro Etage
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

# --- Summiertes Gesamtergebnis über alle Etagen ---
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
