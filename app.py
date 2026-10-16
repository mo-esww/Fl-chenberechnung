import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
import io
import json
from google import genai
from google.genai import types

st.set_page_config(page_title="CAD Flächenheizungs-Auslegung", layout="wide")

st.title("🏠 Automatisierte Flächenheizungsauslegung aus PDF-Plänen")
st.write("Laden Sie Ihren CAD-Plan (PDF) hoch. Die KI liest Räume und Flächen aus und berechnet die überschlägige Fußbodenheizung.")

# Sidebar für API-Key
st.sidebar.header("Konfiguration")
api_key_input = st.sidebar.text_input("Google Gemini API Key", type="password")

# Datei-Upload
uploaded_file = st.file_uploader("CAD-Plan als PDF hochladen", type=["pdf"])

if uploaded_file is not None:
    if not api_key_input:
        st.warning("Bitte geben Sie Ihren Google Gemini API Key in der Seitenleiste ein.")
    else:
        if st.button("Plan analysieren & Auslegung starten", type="primary"):
            with st.spinner("Analysiere Plan mit KI... Bitte einen Moment Geduld."):
                try:
                    # PDF einlesen via PyMuPDF
                    pdf_bytes = uploaded_file.read()
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    page = doc[0]  # Erste Seite
                    pix = page.get_pixmap(dpi=200)
                    bild = Image.open(io.BytesIO(pix.tobytes("png")))
                    
                    # Gemini Client initialisieren
                    client = genai.Client(api_key=api_key_input)
                    
                    prompt = """
                    Analysiere diesen Architektur- oder CAD-Plan. 
                    Deine Aufgabe ist es, alle auf dem Plan verzeichneten Räume mit ihrer Bezeichnung und ihrer Fläche in Quadratmetern (m²) zu extrahieren.
                    Erkenne zudem anhand der Raumbezeichnung die Nutzungsart (z.B. Bad, Wohnen, Schlafzimmer, Flur, Küche, Büro).
                    
                    Gib das Ergebnis AUSSCHLIESSLICH als valides JSON-Array im folgenden Format zurück, ohne zusätzlichen Markdown-Text:
                    [
                      {
                        "raum_name": "Wohnen / Essen",
                        "nutzungstyp": "Wohnen",
                        "flaeche_m2": 35.5
                      }
                    ]
                    """
                    
                    # Aktualisiertes Modell laut API-Fehlermeldung
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[bild, prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json"),
                    )
                    
                    raeume_data = json.loads(response.text)
                    
                    # Berechnungslogik
                    ergebnisse = []
                    temperaturen = {"Bad": 24.0, "Wohnen": 20.0, "Küche": 20.0, "Büro": 20.0, "Schlafen": 18.0, "Flur": 18.0, "Standard": 20.0}
                    
                    for raum in raeume_data:
                        name = raum.get("raum_name", "Unbekannt")
                        nutzung = raum.get("nutzungstyp", "Standard")
                        flaeche = float(raum.get("flaeche_m2", 0.0))
                        
                        soll_temp = temperatures.get(nutzung, temperatures["Standard"])
                        spez_last = 50.0 if nutzung == "Bad" else 35.0
                        heizlast_watt = flaeche * spez_last
                        
                        if spez_last > 45 or nutzung == "Bad":
                            va = 10
                        elif spez_last > 30:
                            va = 15
                        else:
                            va = 20
                            
                        rohr_m = round(flaeche * (100 / va) * 1.15, 1)

                        ergebnisse.append({
                            "Raumbezeichnung": name,
                            "Nutzungsart": nutzung,
                            "Fläche [m²]": flaeche,
                            "Soll-Temp [°C]": soll_temp,
                            "Heizlast [W]": round(heizlast_watt, 1),
                            "Verlegeabstand [cm]": va,
                            "Rohrlauf [m]": rohr_m
                        })
                        
                    df = pd.DataFrame(ergebnisse)
                    
                    # Erfolg ausgeben
                    st.success(f"Erfolgreich {len(df)} Räume erkannt!")
                    st.dataframe(df, use_container_width=True)
                    
                    # Excel Download vorbereiten
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Heizungsauslegung')
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="📥 Excel-Tabelle herunterladen",
                        data=excel_data,
                        file_name="heizungsauslegung.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                except Exception as e:
                    st.error(f"Ein Fehler ist aufgetreten: {e}")
