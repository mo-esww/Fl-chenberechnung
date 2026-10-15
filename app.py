import streamlit as st
import pandas as pd
import numpy as np
import pypdf
import re

# --- Seiten-Konfiguration & Corporate Design ---
st.set_page_config(
    page_title="Wärmepumpen- & Fußbodenheizungs-Rechner", 
    page_icon="🔥", 
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
    st.title("Wärmepumpen-Konfigurator & Fußbodenheizungs-Planer")
    st.markdown("*Interaktive Auslegung, Baureihen-Wahl und Begrenzung des Bivalenzpunkts auf max. -3°C*")
    st.markdown("*Ersetzt keine Heizlastberechnung nach Norm 12831*")

st.markdown("---")

# --- Tabs für die Navigation ---
tab_wp, tab_fbh = st.tabs(["🔥 Wärmepumpen & Bivalenzpunkt", "📐 Fußbodenheizung & Etagen-Planung"])

# ==========================================
# TAB 1: WÄRMEPUMPEN & BIVALENZPUNKT
# ==========================================
with tab_wp:
    x_vals = list(range(-18, 23, 2))

    kennlinien_db_ahpa = {
        "AHPA 412": {
            35: [6.2, 6.6, 7.0, 7.4, 7.8, 8.2, 8.6, 9.1, 9.6, 10.1, 10.6, 11.1, 11.6, 12.1, 12.7, 13.3, 13.9, 14.5, 15.1, 15.6, 16.0],
            55: [6.1, 6.4, 6.7, 7.0, 7.3, 7.6, 7.9, 8.3, 8.7, 9.1, 9.5, 9.9, 10.3, 10.8, 11.3, 11.8, 12.3, 12.8, 13.4, 14.0, 14.5]
        },
        "AHPA 413": {
            35: [7.2, 7.7, 8.2, 8.7, 9.1, 9.6, 10.1, 10.7, 11.2, 11.7, 12.2, 12.8, 13.5, 14.4, 15.2, 16.0, 16.8, 17.6, 18.2, 18.7, 18.7],
            55: [7.0, 7.4, 7.8, 8.2, 8.6, 9.1, 9.6, 10.1, 10.7, 11.2, 11.7, 12.3, 12.9, 13.5, 14.2, 15.0, 15.8, 16.4, 17.0, 17.0, 17.2]
        },
        "AHPA 618": {
            35: [10.5, 11.0, 11.6, 12.2, 12.8, 13.5, 14.3, 15.1, 15.9, 16.7, 17.5, 18.3, 19.1, 20.0, 20.9, 21.8, 22.7, 23.6, 24.5, 25.4, 26.4],
            55: [10.4, 10.8, 11.3, 11.8, 12.3, 12.9, 13.5, 14.2, 14.9, 15.6, 16.3, 17.0, 17.7, 18.5, 19.3, 20.1, 20.9, 21.7, 22.5, 23.3, 24.0]
        },
        "AHPA 722": {
            35: [11.8, 12.5, 13.2, 13.9, 14.6, 15.4, 16.2, 16.5, 16.8, 17.1, 17.5, 19.0, 21.0, 23.2, 25.5, 27.5, 29.5, 31.5, 33.5, 35.5, 37.0],
            55: [10.6, 11.3, 12.0, 12.6, 13.2, 13.8, 14.3, 14.3, 14.4, 14.5, 14.6, 16.0, 18.0, 19.8, 21.6, 23.2, 24.8, 26.4, 28.0, 29.5, 30.8]
        },
        "AHPA 1030": {
            35: [16.5, 17.5, 18.5, 19.5, 21.0, 22.5, 24.0, 24.8, 25.5, 26.2, 27.0, 30.0, 34.0, 38.0, 42.0, 45.8, 49.5, 53.0, 56.5, 60.0, 63.0],
            55: [16.2, 17.0, 17.8, 18.6, 19.8, 21.0, 22.2, 22.8, 23.3, 23.8, 24.2, 27.0, 31.0, 34.8, 38.5, 41.8, 45.2, 48.5, 51.8, 55.0, 58.0]
        }
    }

    kennlinien_db_ahpc = {
        "AHPC 27": {
            35: [4.7, 5.0, 5.3, 5.7, 6.1, 6.5, 7.0, 7.5, 8.0, 7.9, 7.9, 8.3, 8.7, 9.1, 9.5, 10.0, 10.1, 10.3, 10.4, 10.6, 10.7],
            55: [4.5, 4.8, 5.1, 5.5, 5.9, 6.3, 6.8, 7.0, 7.1, 7.1, 7.1, 7.5, 8.0, 8.4, 8.8, 9.0, 9.2, 9.3, 9.5, 9.6, 9.7]
        },
        "AHPC 412": {
            35: [7.6, 8.0, 8.5, 9.0, 9.5, 10.0, 10.6, 11.2, 11.8, 12.5, 13.0, 13.5, 14.2, 14.9, 15.6, 16.5, 16.8, 17.1, 17.4, 17.7, 18.0],
            55: [7.2, 7.6, 8.0, 8.5, 9.0, 9.5, 10.1, 10.8, 11.5, 12.2, 12.5, 13.1, 13.8, 14.5, 15.2, 16.0, 16.3, 16.6, 16.9, 17.2, 17.4]
        }
    }

    st.subheader("1. Gebäudedaten & Parameter")
    col_input1, col_input2 = st.columns(2)

    with col_input1:
        auswahl_modus = st.radio(
            "Wie möchten Sie die Heizlast ermitteln?",
            [
                "1. Über Gebäudestandard & Wohnfläche (Standard)",
                "2. Anhand fossilem Brennstoffverbrauch (Öl / Gas)",
                "3. Direkte Heizlast-Vorgabe (z.B. nach DIN 12831)"
            ]
        )

        heizlast_watt = 0.0
        if auswahl_modus.startswith("1."):
            wohnflaeche = st.number_input("Beheizte Wohnfläche (m²)", min_value=20, max_value=1000, value=160, step=10)
            baujahr = st.selectbox("Baujahr / Dämmstandard", [1950, 1970, 1980, 1990, 2000, 2010, 2016])
            heizlast_tabelle = {1950: 160.0, 1970: 130.0, 1980: 110.0, 1990: 90.0, 2000: 70.0, 2010: 50.0, 2016: 40.0}
            spez_heizlast = heizlast_tabelle.get(baujahr, 50.0)
            heizlast_watt = wohnflaeche * spez_heizlast
            personen = st.selectbox("Anzahl Personen im Haushalt", [1, 2, 3, 4, 5, 6, 7], key="pers_wp")

        elif auswahl_modus.startswith("2."):
            brennstoff_art = st.selectbox("Brennstoffart", ["Heizöl (Liter/Jahr)", "Erdgas (kWh/Jahr)", "Flüssiggas (Liter/Jahr)"])
            verbrauch = st.number_input("Jahresverbrauch", min_value=500, max_value=100000, value=2500, step=100)
            if "Heizöl" in brennstoff_art:
                jaehrliche_waermearbeit = verbrauch * 10 * 0.85
            elif "Erdgas" in brennstoff_art:
                jaehrliche_waermearbeit = verbrauch * 0.85
            else:
                jaehrliche_waermearbeit = verbrauch * 6.5 * 0.85
            heizlast_watt = (jaehrliche_waermearbeit / 2000) * 1000
            personen = st.selectbox("Anzahl Personen im Haushalt", [1, 2, 3, 4, 5, 6, 7], key="pers_wp2")

        else:
            heizlast_kw = st.number_input("Vorhandene Heizlast / Vorgabe (kW)", min_value=2.0, max_value=100.0, value=10.0, step=0.5)
            heizlast_watt = heizlast_kw * 1000.0
            personen = st.selectbox("Anzahl Personen im Haushalt", [1, 2, 3, 4, 5, 6, 7], key="pers_wp3")

    with col_input2:
        st.markdown("### Klimadaten & Baureihe")
        baureihe_wahl = st.selectbox("Wärmepumpen-Baureihe", ["AHPA", "AHPC"])
        t_norm = st.number_input("Norm-Außentemperatur (T_norm) [°C]", min_value=-25.0, max_value=0.0, value=-12.0, step=1.0)
        t_grenz = st.number_input("Heizgrenztemperatur (T_grenz) [°C]", min_value=10.0, max_value=20.0, value=15.0, step=1.0)
        systemtemperatur = st.selectbox("Systemtemperatur / Vorlauf [°C]", [35, 55])
        ww_bereitung = st.selectbox("Warmwasserbereitung", ["ja", "nein"])
        frischwasser = st.selectbox("Frischwassermodul", ["nein", "ja"])

    ww_aufschlag = (personen * 500) if ww_bereitung == "ja" else 0
    gesamt_last_kw = (heizlast_watt + ww_aufschlag) / 1000.0

    aktive_db = kennlinien_db_ahpa if baureihe_wahl == "AHPA" else kennlinien_db_ahpc
    ergebnisse_liste = []

    for wp_name, daten in aktive_db.items():
        wp_leistungen = daten[systemtemperatur]
        biv_punkt = 99.0
        leistung_biv = 0.0
        last_werte = [gesamt_last_kw * (t_grenz - x) / (t_grenz - t_norm) for x in x_vals]
        differenzen = [wp_l - l_w for wp_l, l_w in zip(wp_leistungen, last_werte)]
        
        for i in range(len(x_vals) - 1):
            if differenzen[i] * differenzen[i+1] <= 0:
                x1, x2 = x_vals[i], x_vals[i+1]
                d1, d2 = differenzen[i], differenzen[i+1]
                if d1 != d2:
                    biv_punkt = x1 - d1 * (x2 - x1) / (d2 - d1)
                    leistung_biv = wp_leistungen[i] + (biv_punkt - x1) / (x2 - x1) * (wp_leistungen[i+1] - wp_leistungen[i])
                else:
                    biv_punkt = x1
                    leistung_biv = wp_leistungen[i]
                break
                
        if biv_punkt == 99.0 and differenzen[0] >= 0:
            biv_punkt = -18.0
            leistung_biv = wp_leistungen[0]
        elif biv_punkt == 99.0:
            biv_punkt = 22.0
            leistung_biv = wp_leistungen[-1]

        ergebnisse_liste.append({
            "Modell": wp_name,
