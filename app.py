import streamlit as st
import pandas as pd
import numpy as np

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
    st.markdown("*Etagenbasierte Raumplanung, Rohrnetz-Dimensionierung & Kreise-Zuordnung*")
    st.markdown("Ersetzt keine Heizlastberechnung nach Norm 12831")

st.markdown("---")

# ==========================================
# FUSSBODENHEIZUNG & MEHR-ETAGEN-PLANUNG
# ==========================================
st.subheader("📐 Raum- und Etagen-Management (UG, EG, OG, DG)")
st.markdown("Da CAD-Pläne oft komplexe Text-Ebenen nutzen, verwalten und bearbeiten Sie Ihre Räume hier direkt verlustfrei und übersichtlich in den etagenbezogenen Tabellen.")

etagen_definitionen = {
    "UG": "Untergeschoss / Keller",
    "EG": "Erdgeschoss",
    "OG": "Obergeschoss",
    "DG": "Dachgeschoss"
}

# Initialisierung der Tabellen im Session State (falls noch nicht vorhanden)
if "etagen_daten" not in st.session_state:
    st.session_state.etagen_daten = {
        "UG": [],
        "EG": [
            {"Raumbezeichnung": "Essen / Wohnen", "Fläche [m²]": 55.04, "Verlegeabstand [cm]": 15, "Heizkreise": 3},
            {"Raumbezeichnung": "Küche", "Fläche [m²]": 17.81, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
            {"Raumbezeichnung": "Diele", "Fläche [m²]": 13.50, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
            {"Raumbezeichnung": "Duschbad", "Fläche [m²]": 5.70, "Verlegeabstand [cm]": 10, "Heizkreise": 1},
        ],
        "OG": [
            {"Raumbezeichnung": "Schlafen", "Fläche [m²]": 16.08, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
            {"Raumbezeichnung": "Kind 1", "Fläche [m²]": 17.91, "Verlegeabstand [cm]": 15, "Heizkreise": 1},
            {"Raumbezeichnung": "Bad", "Fläche [m²]": 9.66, "Verlegeabstand [cm]": 10, "Heizkreise": 1},
        ],
        "DG": []
    }

# Optionaler Upload-Hinweis (damit der Nutzer weiß, dass er Dateien ablegen kann)
st.file_uploader("Pläne zur Dokumentation hochladen (PDF)", type=["pdf"], accept_multiple_files=True, key="pdf_upload_dummy")

# --- Dynamische Anzeige und Editierung für jede Etage ---
etagen_ergebnisse = {}

for etage_key, etage_titel in etagen_definitionen.items():
    st.markdown(f"### 🏢 {etage_titel} ({etage_key})")
    
    df_etage = pd.DataFrame(st.session_state.etagen_daten[etage_key])
    
    # Interaktiver Editor für den Anwender
    edited_df = st.data_editor(
        df_etage, 
        num_rows="dynamic", 
        use_container_width=True, 
        key=f"editor_{etage_key}",
        placeholder="Klicken Sie hier, um Räume hinzuzufügen..."
    )
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
