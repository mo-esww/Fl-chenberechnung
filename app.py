import streamlit as st
import pandas as pd
import numpy as np
import fitz  # PyMuPDF für PDF-zu-Bild Konvertierung
import pytesseract  # OCR-Texterkennung direkt auf dem JPG
from PIL import Image
import io
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
    st.markdown("*PDF-Upload, JPG-Konvertierung & automatische OCR-Raumerfassung*")
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

st.subheader("📐 PDF-Upload, JPG-Konvertierung & OCR-Raumanalyse")
st.markdown("Laden Sie Ihre Plan-PDFs hoch. Die App konvertiert sie zu JPGs und liest die Räume per Texterkennung aus.")

uploaded_files = st.file_uploader("Grundrisse hochladen (PDF)", type=["pdf"], accept_multiple_files=True, key="pdf_ocr_upload")

if uploaded_files:
    st.markdown("### 🗂️ Konvertierte Pläne & Etagen-Zuweisung")
    file_assignments = {}
    
    if "converted_data" not in st.session_state:
        st.session_state.converted_data = {}

    for uploaded_file in uploaded_files:
        if uploaded_file.name not in st.session_state.converted_data:
            try:
                pdf_bytes = uploaded_file.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                
                page_images = []
                for page in doc:
                    # Höhere DPI (200) für optimale OCR-Erkennung von CAD-Zahlen
                    pix = page.get_pixmap(dpi=200)
                    img_data = pix.tobytes("jpg")
                    image = Image.open(io.BytesIO(img_data))
                    page_images.append(image)
                
                st.session_state.converted_data[uploaded_file.name] = page_images
            except Exception as e:
                st.error(f"Fehler bei der Verarbeitung von {uploaded_file.name}: {e}")

    cols = st.columns(len(uploaded_files))
    for idx, uploaded_file in enumerate(uploaded_files):
        with cols[idx % len(cols)]:
            st.markdown(f"**📄 Datei:** `{uploaded_file.name}`")
            
            if uploaded_file.name in st.session_state.converted_data:
                for page_idx, img in enumerate(st.session_state.converted_data[uploaded_file.name]):
                    st.image(img, caption=f"Seite {page_idx+1} (JPG-Ansicht)", use_container_width=True)

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

    if st.button("🔄 Pläne per OCR auslesen & Tabellen befüllen"):
        temp_etagen = {k: [] for k in etagen_definitionen.keys()}
        
        try:
            for uploaded_file in uploaded_files:
                target_etage = file_assignments[uploaded_file.name]
                if uploaded_file.name in st.session_state.converted_data:
                    for img in st.session_state.converted_data[uploaded_file.name]:
                        # OCR direkt auf das konvertierte JPG anwenden (Deutsch)
                        ocr_text = pytesseract.image_to_string(img, lang='deu')
                        lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
                        
                        for i, line in enumerate(lines):
                            if "m²" in line or "m 2" in line or "F:" in line or "m2" in line:
                                match = re.search(r'([0-9.,]+)\s*(?:m[²2]|m\s*2)', line)
                                if not match and "F:" in line:
                                    match = re.search(r"F:\s*([0-9.,]+)", line)
                                    
                                if match:
                                    try:
                                        val_str = match.group(1).replace(',', '.')
                                        area = float(val_str)
                                        
                                        if 1.0 < area < 500:
                                            room_name = ""
                                            clean_line = re.sub(r'[0-9.,]+\s*m[²2]', '', line).strip()
                                            
                                            if len(clean_line) > 1 and not clean_line.isdigit():
                                                room_name = clean_line
                                            else:
                                                for offset in [-1, 1, -2, 2]:
                                                    idx_check = i + offset
                                                    if 0 <= idx_check < len(lines):
                                                        candidate = lines[idx_check]
                                                        if not any(kw in candidate for kw in ["m²", "m 2", "Allplan", "Beetzendorf", "Blatt", "ÜNN", "H/B", "Architekt", "DATUM", "PROJEKT", "BAUHERR", "Vorabzug"]):
                                                            room_name = candidate
                                                            break
                                            
                                            if not room_name or room_name.replace('.', '', 1).isdigit():
                                                room_name = "Raum"

                                            room_name = room_name.replace("m²", "").strip()

                                            va = 10 if any(b in room_name.lower() for b in ["bad", "wc", "duschbad"]) else 15
                                            
                                            rohr_gesamt = area * (100.0 / va + 1.5)
                                            kreise = 1
                                            while (rohr_gesamt / kreise) > 125.0:
                                                kreise += 1

                                            existing_areas = [r["Fläche [m²]"] for r in temp_etagen[target_etage]]
                                            if area not in existing_areas:
                                                temp_etagen[target_etage].append({
                                                    "Status": "Beheizt",
                                                    "Raumbezeichnung": room_name,
                                                    "Fläche [m²]": area,
                                                    "Verlegeabstand [cm]": va,
                                                    "Heizkreise": kreise
                                                })
                                    except ValueError:
                                        pass
                                        
            st.session_state.etagen_daten = temp_etagen
            st.success("OCR-Auswertung erfolgreich abgeschlossen! Die Tabellen wurden befüllt.")
        except Exception as e:
            st.error(f"Fehler bei der OCR-Auswertung: {e}")
else:
    st.session_state.etagen_daten = {k: [] for k in etagen_definitionen.keys()}
    if "converted_data" in st.session_state:
        del st.session_state.converted_data

st.markdown("---")

spalten_struktur = {
    "Status": [],
    "Raumbezeichnung": [],
    "Fläche [m²]": [],
    "Verlegeabstand [cm]": [],
    "Heizkreise": []
}

# --- Dynamische Anzeige und Editierung für jede Etage ---
etagen_ergebnisse = {}
warnungen_gesamt = []

for etage_key, etage_titel in etagen_definitionen.items():
    st.markdown(f"### 🏢 {etage_titel} ({etage_key})")
    
    current_data = st.session_state.etagen_daten[etage_key]
    if not current_data:
        df_etage = pd.DataFrame(columns=list(spalten_struktur.keys()))
    else:
        df_etage = pd.DataFrame(data=current_data)
        if "Status" not in df_etage.columns:
            df_etage.insert(0, "Status", "Beheizt")
    
    num_rows = len(df_etage) if not df_etage.empty else 1
    editor_height = int((num_rows + 2) * 38) + 40
    
    edited_df = st.data_editor(
        df_etage, 
        num_rows="dynamic", 
        use_container_width=True, 
        height=editor_height,
        key=f"editor_{etage_key}",
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Status",
                help="Wählen Sie aus, ob der Raum beheizt oder unbeheizt ist.",
                options=["Beheizt", "Unbeheizt"],
                required=True,
                default="Beheizt"
            )
        },
        placeholder="Klicken Sie oben auf den Auslesen-Button oder fügen Sie Räume hinzu..."
    )
    
    st.session_state.etagen_daten[etage_key] = edited_df.to_dict('records')
    
    e_flaeche = 0
    e_unbeheizt = 0
    e_kreise = 0
    e_rohr = 0
    
    if not edited_df.empty and "Status" in edited_df.columns and "Fläche [m²]" in edited_df.columns:
        df_active = edited_df[edited_df["Status"] == "Beheizt"]
        df_inactive = edited_df[edited_df["Status"] == "Unbeheizt"]
        
        e_flaeche = df_active["Fläche [m²]"].sum() if not df_active.empty else 0
        e_unbeheizt = df_inactive["Fläche [m²]"].sum() if not df_inactive.empty else 0
        e_kreise = int(df_active["Heizkreise"].sum()) if not df_active.empty and "Heizkreise" in df_active.columns else 0
        
        if not df_active.empty and "Verlegeabstand [cm]" in df_active.columns and "Heizkreise" in df_active.columns:
            for _, row in df_active.iterrows():
                va = row.get("Verlegeabstand [cm]", 0)
                fl = row.get("Fläche [m²]", 0)
                kr = row.get("Heizkreise", 1)
                room_name = row.get("Raumbezeichnung", "Unbekannt")
                
                if pd.notna(va) and pd.notna(fl) and va > 0:
                    raum_rohr = fl * (100.0 / va + 1.5)
                    e_rohr += raum_rohr
                    
                    if kr > 0:
                        rohr_pro_kreis = raum_rohr / kr
                        if rohr_pro_kreis > 125.0:
                            warnung_txt = f"⚠️ **{etage_key} - {room_name}**: Ein Heizkreis hat ca. {rohr_pro_kreis:.1f} m (Limit: 125 m). Bitte Heizkreise auf mindestens {np.ceil(raum_rohr / 125.0):.0f} erhöhen!"
                            warnungen_gesamt.append(warnung_txt)
    
    etagen_ergebnisse[etage_key] = {
        "flaeche": e_flaeche, 
        "unbeheizt": e_unbeheizt, 
        "kreise": e_kreise, 
        "rohr": e_rohr
    }
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label=f"Beheizte Fläche {etage_key}", value=f"{e_flaeche:.2f} m²")
    with col2:
        st.metric(label=f"Unbeheizte Fläche {etage_key}", value=f"{e_unbeheizt:.2f} m²")
    with col3:
        st.metric(label=f"Heizkreise {etage_key}", value=f"{e_kreise} Kreise")
    with col4:
        st.metric(label=f"Rohrbedarf {etage_key}", value=f"{e_rohr:.0f} m")
        
    st.markdown("---")

if warnungen_gesamt:
    st.error("### ⚠️ Hinweis zur max. Heizkreislänge (125m)")
    for w in warnungen_gesamt:
        st.warning(w)
    st.markdown("---")

# --- Summiertes Gesamtergebnis ---
total_flaeche = sum([res["flaeche"] for res in etagen_ergebnisse.values()])
total_unbeheizt = sum([res["unbeheizt"] for res in etberg_ergebnisse.values()] if 'etberg_ergebnisse' in locals() else [res["unbeheizt"] for res in etagen_ergebnisse.values()])
total_rohr = sum([res["rohr"] for res in etagen_ergebnisse.values()])
kreise_str = " | ".join([f"{k}: {res['kreise']}" for k, res in etagen_ergebnisse.items() if res['kreise'] > 0])

st.subheader("📈 Summiertes Gesamtergebnis (Gesamtgebäude)")
col_f1, col_f2, col_f3, col_f4 = st.columns(4)
with col_f1:
    st.metric(label="Gesamt-Beheizte Fläche", value=f"{total_flaeche:.2f} m²")
with col_f2:
    st.metric(label="Gesamt-Unbeheizte Fläche", value=f"{total_unbeheizt:.2f} m²")
with col_f3:
    st.metric(label="Heizkreise je Verteiler", value=kreise_str if kreise_str else "0 Kreise")
with col_f4:
    st.metric(label="Gesamter Rohrbedarf", value=f"{total_rohr:.0f} m")
