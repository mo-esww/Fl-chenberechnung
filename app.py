import streamlit as st
import pandas as pd
import numpy as np
import fitz  # PyMuPDF für High-Performance PDF-zu-Bild-Konvertierung (ohne Poppler-Abhängigkeit)
from PIL import Image
import io

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
    st.markdown("*PDF-Upload mit automatischer JPG-Konvertierung für präzise Raum-Erfassung*")
    st.markdown("Ersetzt keine Heizlastberechnung nach Norm 12831")

st.markdown("---")

etagen_definitionen = {
    "UG": "Untergeschoss / Keller",
    "EG": "Erdgeschoss",
    "OG": "Obergeschoss",
    "DG": "Dachgeschoss"
}

# Initialisierung der Tabellen im Session State (standardmäßig leer)
if "etagen_daten" not in st.session_state:
    st.session_state.etagen_daten = {k: [] for k in etagen_definitionen.keys()}

st.subheader("📐 PDF-Upload & Automatische JPG-Konvertierung")
st.markdown("Laden Sie Ihre Plan-PDFs hoch. Die App wandelt diese im Hintergrund in hochauflösende JPG-Bilder um.")

# PDF-Uploader
uploaded_files = st.file_uploader("Grundrisse hochladen (PDF)", type=["pdf"], accept_multiple_files=True, key="pdf_to_jpg_upload")

if uploaded_files:
    st.markdown("### 🗂️ Konvertierte JPG-Ansicht & Etagen-Zuweisung")
    file_assignments = {}
    
    if "converted_jpgs" not in st.session_state:
        st.session_state.converted_jpgs = {}

    for uploaded_file in uploaded_files:
        if uploaded_file.name not in st.session_state.converted_jpgs:
            try:
                # PDF-Bytes direkt über PyMuPDF in Bilder konvertieren
                pdf_bytes = uploaded_file.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                
                page_images = []
                for page in doc:
                    pix = page.get_pixmap(dpi=150)
                    img_data = pix.tobytes("jpg")
                    image = Image.open(io.BytesIO(img_data))
                    page_images.append(image)
                
                st.session_state.converted_jpgs[uploaded_file.name] = page_images
            except Exception as e:
                st.error(f"Fehler bei der JPG-Konvertierung von {uploaded_file.name}: {e}")

    cols = st.columns(len(uploaded_files))
    for idx, uploaded_file in enumerate(uploaded_files):
        with cols[idx % len(cols)]:
            st.markdown(f"**📄 Datei:** `{uploaded_file.name}`")
            
            # Zeige die konvertierten JPG-Seiten als Vorschau
            if uploaded_file.name in st.session_state.converted_jpgs:
                for page_idx, img in enumerate(st.session_state.converted_jpgs[uploaded_file.name]):
                    st.image(img, caption=f"Seite {page_idx+1} (als JPG konvertiert)", use_container_width=True)

            # Intelligente Vorauserkennung für das Etagen-Dropdown
            default_idx = 1
            fn_upper = uploaded_file.name.upper()
            if "UG" in fn_upper or "KELLER" in fn_upper: default_idx = 0
            elif "EG" in fn_upper: default_idx = 1
            elif "OG" in fn_upper: default_idx = 2
            elif "DG" in fn_upper or "DACH" in fn_upper: default_idx = 3

            chosen_etage = st.selectbox(
                "Ziel-Etage wählen:",
                options=list(etagen_definitionen.keys()),
                index=default_idx,
                format_func=lambda x: etagen_definitionen[x],
                key=f"assign_{uploaded_file.name}"
            )
            file_assignments[uploaded_file.name] = chosen_etage

    if st.button("🔄 Konvertierte Pläne übernehmen"):
        st.success("PDFs wurden erfolgreich in JPGs konvertiert und den Etagen zugewiesen!")
else:
    st.session_state.etagen_daten = {k: [] for k in etagen_definitionen.keys()}
    if "converted_jpgs" in st.session_state:
        del st.session_state.converted_jpgs

st.markdown("---")

spalten_struktur = {
    "Raumbezeichnung": [],
    "Fläche [m²]": [],
    "Verlegeabstand [cm]": [],
    "Heizkreise": []
}

# --- Dynamische Anzeige und Editierung für jede Etage ---
etagen_ergebnisse = {}

for etage_key, etage_titel in etagen_definitionen.items():
    st.markdown(f"### 🏢 {etage_titel} ({etage_key})")
    
    current_data = st.session_state.etagen_daten[etage_key]
    if not current_data:
        df_etage = pd.DataFrame(columns=list(spalten_struktur.keys()))
    else:
        df_etage = pd.DataFrame(current_data)
    
    edited_df = st.data_editor(
        df_etage, 
        num_rows="dynamic", 
        use_container_width=True, 
        key=f"editor_{etage_key}",
        placeholder="Klicken Sie hier, um Räume hinzuzufügen..."
    )
    
    st.session_state.etagen_daten[etage_key] = edited_df.to_dict('records')
    
    e_flaeche = edited_df["Fläche [m²]"].sum() if not edited_df.empty and "Fläche [m²]" in edited_df.columns else 0
    e_kreise = int(edited_df["Heizkreise"].sum()) if not edited_df.empty and "Heizkreise" in edited_df.columns else 0
    
    e_rohr = 0
    if not edited_df.empty and "Verlegeabstand [cm]" in edited_df.columns and "Fläche [m²]" in edited_df.columns:
        for _, row in edited_df.iterrows():
            va = row.get("Verlegeabstand [cm]", 0)
            fl = row.get("Fläche [m²]", 0)
            if pd.notna(va) and pd.notna(fl) and va > 0:
                e_rohr += fl * (100.0 / va + 1.5)
    
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
