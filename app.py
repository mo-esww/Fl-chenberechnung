"""Überschlägige Flächenheizungs-Auslegung aus Raum-/Flächenlisten (Excel, CSV, PDF).

Alle Rechenwerte sind Näherungen für die frühe Planungsphase (LP 2/3) und
ersetzen KEINE Heizlastberechnung nach DIN EN 12831 bzw. Auslegung nach DIN EN 1264.
"""
import io
import math
import re

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    import pdfplumber
except ImportError:  # PDF-Import optional
    pdfplumber = None

st.set_page_config(page_title="Flächenheizung – Überschlag", layout="wide")

# ----------------------------------------------------------------------------
# 1) Einlesen & Normalisieren
# ----------------------------------------------------------------------------
SYNONYME = {
    "Raumnr": ["raumnr", "raum-nr", "raumnummer", "r-nr", "nr", "nummer", "pos"],
    "Fläche m²": ["fläche", "flaeche", "nutzfläche", "grundfläche", "nf", "fl.",
                  "area", "m²", "m2", "qm", "wohnfläche"],
    "Geschoss": ["geschoss", "ebene", "etage", "level", "stockwerk", "gesch."],
    "Raum": ["raumbezeichnung", "bezeichnung", "raumname", "raum", "nutzung",
             "name", "room", "raumart"],
}

GESCHOSS_RE = re.compile(
    r"\b(UG|KG|EG|DG|\d?\.?\s?OG\s?\d?|Untergeschoss|Kellergeschoss|Erdgeschoss|"
    r"Obergeschoss|Dachgeschoss)\b", re.I)

ZEILE_RE = re.compile(
    r"^\s*(?:(?P<nr>[A-Za-z]{0,3}\d[\d.\-/]*)\s+)?"
    r"(?P<name>[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9 .\-/()]{1,40}?)\s+"
    r"(?P<flaeche>\d{1,4}[.,]\d{1,2})\s*(?:m²|m2|qm)?\s*$"
)


def zahl(x):
    """'12,34', '12.34 m²', '1.234,56' -> float."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return None if pd.isna(x) else float(x)
    s = str(x).lower()
    for u in ("m²", "m2", "qm"):
        s = s.replace(u, "")
    s = re.sub(r"[^\d,.\-]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def normalisiere(df: pd.DataFrame):
    """Spalten anhand von Synonymen zuordnen. Gibt None zurück, wenn Raum+Fläche fehlen."""
    df = df.copy()
    df.columns = [str(c).strip().lower() if c is not None else "" for c in df.columns]
    zuordnung, belegt = {}, set()
    for ziel in ["Raumnr", "Fläche m²", "Geschoss", "Raum"]:
        syn = SYNONYME[ziel]
        treffer = next((c for c in df.columns if c in syn and c not in belegt), None)
        if treffer is None:
            treffer = next((c for c in df.columns
                            if c not in belegt and any(s in c for s in syn)), None)
        if treffer:
            zuordnung[ziel] = treffer
            belegt.add(treffer)
    if "Raum" not in zuordnung or "Fläche m²" not in zuordnung:
        return None
    out = pd.DataFrame({
        "Geschoss": df[zuordnung["Geschoss"]] if "Geschoss" in zuordnung else "",
        "Raumnr": df[zuordnung["Raumnr"]] if "Raumnr" in zuordnung else "",
        "Raum": df[zuordnung["Raum"]].astype(str).str.strip(),
        "Fläche m²": df[zuordnung["Fläche m²"]].map(zahl),
    })
    out = out[out["Fläche m²"].notna() & (out["Fläche m²"] > 0)]
    out = out[~out["Raum"].str.lower().str.contains("summe|gesamt|total", na=False)]
    return out


def lese_tabelle(datei) -> pd.DataFrame:
    name = datei.name.lower()
    teile = []
    if name.endswith(".csv"):
        roh = pd.read_csv(datei, sep=None, engine="python", dtype=str)
        n = normalisiere(roh)
        if n is not None:
            teile.append(n)
    else:
        for blatt, roh in pd.read_excel(datei, sheet_name=None, dtype=str).items():
            n = normalisiere(roh)
            if n is not None:
                if (n["Geschoss"].astype(str).str.strip() == "").all():
