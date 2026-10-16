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
                    n["Geschoss"] = blatt
                teile.append(n)
    return pd.concat(teile, ignore_index=True) if teile else pd.DataFrame()


FL_RE = re.compile(r"^(?:A\s*=\s*)?(\d{1,4}[.,]\d{1,2})\s*(?:m²|m2|qm)$", re.I)
NR_RE = re.compile(r"^[A-Za-z]{0,3}\d[\d.\-/]*$")
NAME_RE = re.compile(r"[A-Za-zÄÖÜäöüß]{3,}")


def _bloecke(seite, tol_y=3, gap_faktor=1.2):
    """Wörter einer PDF-Seite zu Textblöcken (zusammenhängende Zeilenstücke) gruppieren."""
    woerter = seite.extract_words(keep_blank_chars=False, use_text_flow=False)
    zeilen = []
    for w in sorted(woerter, key=lambda w: w["top"]):
        for z in zeilen:
            if abs(z[0]["top"] - w["top"]) <= tol_y:
                z.append(w)
                break
        else:
            zeilen.append([w])
    bloecke = []
    for z in zeilen:
        z.sort(key=lambda w: w["x0"])
        akt = None
        for w in z:
            h = w["bottom"] - w["top"]
            if akt and w["x0"] - akt["x1"] <= gap_faktor * h:
                akt["text"] += " " + w["text"]
                akt["x1"] = w["x1"]
            else:
                if akt:
                    bloecke.append(akt)
                akt = {"text": w["text"], "x0": w["x0"], "x1": w["x1"],
                       "top": w["top"], "bottom": w["bottom"]}
        if akt:
            bloecke.append(akt)
    return bloecke


def lese_stempel(seite, geschoss, max_dx=70, max_dy=60):
    """CAD-Raumstempel: Fläche (mit Einheit) suchen, Name/Nr. darüber oder links zuordnen."""
    bl = _bloecke(seite)
    ergebnis = []
    for f in bl:
        if not FL_RE.match(f["text"].strip()):
            continue
        cx = (f["x0"] + f["x1"]) / 2
        name, nr = None, None
        best_n, best_r = 1e9, 1e9
        for c in bl:
            if c is f:
                continue
            t = c["text"].strip()
            ccx = (c["x0"] + c["x1"]) / 2
            dy = f["top"] - c["bottom"]
            darueber = -3 <= dy <= max_dy and abs(ccx - cx) <= max_dx
            links = abs(c["top"] - f["top"]) <= 3 and 0 <= f["x0"] - c["x1"] <= 80
            if not (darueber or links):
                continue
            dist = abs(dy) + abs(ccx - cx) * 0.3
            if NR_RE.match(t) and dist < best_r:
                nr, best_r = t, dist
            elif NAME_RE.search(t) and not FL_RE.match(t) and dist < best_n:
                name, best_n = t, dist
        if name:
            ergebnis.append({"Geschoss": geschoss, "Raumnr": nr or "", "Raum": name,
                             "Fläche m²": zahl(f["text"])})
    return ergebnis


def lese_zeilen(text, geschoss):
    out = []
    for z in text.splitlines():
        mm = ZEILE_RE.match(z)
        if mm:
            out.append({"Geschoss": geschoss, "Raumnr": mm.group("nr") or "",
                        "Raum": mm.group("name").strip(),
                        "Fläche m²": zahl(mm.group("flaeche"))})
    return out


def lese_ocr(seite, geschoss):
    try:
        import pytesseract
        img = seite.to_image(resolution=300).original
        text = pytesseract.image_to_string(img, lang="deu", config="--psm 6")
    except Exception as e:  # noqa: BLE001
        st.warning(f"OCR nicht verfügbar ({e}). Benötigt pytesseract + Tesseract (deu).")
        return []
    return lese_zeilen(text, geschoss)


def lese_pdf(datei, ocr=False):
    """Mehrstufig: Tabelle -> Textzeilen -> Raumstempel -> (optional) OCR."""
    if pdfplumber is None:
        st.error("pdfplumber ist nicht installiert.")
        return pd.DataFrame(), ""
    teile, methoden = [], set()
    with pdfplumber.open(datei) as pdf:
        for i, seite in enumerate(pdf.pages, 1):
            text = seite.extract_text() or ""
            m = GESCHOSS_RE.search(text)
            geschoss = m.group(0).upper() if m else f"Seite {i}"

            tab_df = []
            for tab in seite.extract_tables():
                if len(tab) < 2:
                    continue
                n = normalisiere(pd.DataFrame(tab[1:], columns=tab[0]))
                if n is not None and not n.empty:
                    if (n["Geschoss"].astype(str).str.strip() == "").all():
                        n["Geschoss"] = geschoss
                    tab_df.append(n)
            if tab_df:
                teile += tab_df
                methoden.add("Tabelle")
                continue

            zeilen = lese_zeilen(text, geschoss)
            if len(zeilen) >= 2:
                teile.append(pd.DataFrame(zeilen))
                methoden.add("Textzeilen")
                continue

            stempel = lese_stempel(seite, geschoss)
            if stempel:
                teile.append(pd.DataFrame(stempel))
                methoden.add("Raumstempel")
                continue

            if ocr and not text.strip():
                z = lese_ocr(seite, geschoss)
                if z:
                    teile.append(pd.DataFrame(z))
                    methoden.add("OCR")
    if not teile:
        return pd.DataFrame(), ""
    df = pd.concat(teile, ignore_index=True)
    df = df.drop_duplicates(subset=["Geschoss", "Raumnr", "Raum", "Fläche m²"])
    return df, ", ".join(sorted(methoden))


# ----------------------------------------------------------------------------
# 2) Raumtyp-Erkennung
# ----------------------------------------------------------------------------
TYPEN = {  # Normraumtemperatur °C (None = nicht beheizt)
    "Wohnen": 20, "Schlafen": 20, "Küche": 20, "Büro": 20, "Flur": 20,
    "WC": 20, "Bad": 24, "Nicht beheizt": None,
}
REGELN = [
    (r"hwr|technik|heizung|abstell|keller|speicher|lager|garage|schacht|aufzug|"
     r"balkon|terrasse|loggia|carport|müll|fahrrad", "Nicht beheizt"),
    (r"\bwc\b|gäste.?wc|toilette", "WC"),
    (r"bad|dusche|sauna|wanne", "Bad"),
    (r"schlaf|eltern|kind", "Schlafen"),
    (r"küche|koch|teeküche", "Küche"),
    (r"büro|arbeit|besprech", "Büro"),
    (r"flur|diele|eingang|garderobe|treppe|vorraum|windfang", "Flur"),
]


def erkenne_typ(name: str) -> str:
    n = name.lower()
    for muster, typ in REGELN:
        if re.search(muster, n):
            return typ
    return "Wohnen"


# ----------------------------------------------------------------------------
# 3) Überschlägige Auslegung
# ----------------------------------------------------------------------------
STANDARDS = {  # spezifische Heizlast bei θe = Normaußentemperatur, W/m² (Richtwerte)
    "Neubau GEG (ca. 40 W/m²)": 40,
    "Effizienzhaus 55 / 40 (ca. 30 W/m²)": 30,
    "Bestand saniert (ca. 60 W/m²)": 60,
    "Bestand teilsaniert (ca. 80 W/m²)": 80,
    "Bestand unsaniert (ca. 100 W/m²)": 100,
}
VA_LISTE = [0.30, 0.25, 0.20, 0.15, 0.10]  # m, vom größten zum kleinsten
ALPHA = 10.8                                # W/(m²K) Wärmeübergang Fußboden
T_FB_MAX = {"Bad": 33.0}                    # sonst 29 °C (Aufenthaltszone)


def r0(va: float) -> float:
    """Grobe Näherung des Wärmewiderstands Rohr/Estrich/Überdeckung in m²K/W."""
    return 0.10 + 0.5 * va


def berechne(df: pd.DataFrame, p: dict) -> pd.DataFrame:
    zeilen = []
    for _, r in df.iterrows():
        ti = TYPEN.get(r["Typ"])
        A = float(r["Fläche m²"])
        z = {"Geschoss": r["Geschoss"], "Raumnr": r["Raumnr"], "Raum": r["Raum"],
             "Typ": r["Typ"], "Fläche m²": A}
        if ti is None:
            z["Status"] = "nicht beheizt"
            zeilen.append(z)
            continue

        faktor_t = (ti - p["te"]) / (20 - p["te"])
        Q = A * p["q_spez"] * faktor_t * (1 + float(r.get("Zuschlag %", 0) or 0) / 100)
        A_bel = A * p["nutz"]
        q_req = Q / A_bel
        q_grenz = ALPHA * (T_FB_MAX.get(r["Typ"], 29.0) - ti)
        dT_h = (p["vl"] - p["spreizung"] / 2) - ti

        va_gew, q_max = None, 0.0
        for va in VA_LISTE:
            q_max = min(dT_h / (p["r_belag"] + r0(va)), q_grenz)
            if q_req <= q_max:
                va_gew = va
                break

        if va_gew is None:
            va_gew = VA_LISTE[-1]
            status = ("Fußbodentemp.-Grenze" if q_req > q_grenz else "VL-Temp. zu niedrig")
            status = f"nicht deckbar ({status})"
        else:
            status = "OK"

        L = A_bel / va_gew
        n_kreise = max(1, math.ceil((L + p["zuleitung"]) / p["max_len"]))
        z.update({
            "θi °C": ti, "Heizlast W": round(Q), "q W/m²": round(q_req, 1),
            "q max W/m²": round(q_max, 1), "VA cm": int(va_gew * 100),
            "Rohrlänge m": round(L + p["zuleitung"]), "Heizkreise": n_kreise,
            "Volumenstrom l/h": round(Q / (1.163 * p["spreizung"])),
            "Status": status,
        })
        zeilen.append(z)
    return pd.DataFrame(zeilen)


def excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Auslegung")
    return buf.getvalue()


# ----------------------------------------------------------------------------
# 4) Oberfläche
# ----------------------------------------------------------------------------
st.title("🔥 Flächenheizung – überschlägige Auslegung")
st.caption("Näherungsrechnung für die frühe Planungsphase – kein Ersatz für "
           "DIN EN 12831 / DIN EN 1264.")

with st.sidebar:
    st.header("Parameter")
    std = st.selectbox("Gebäudestandard", list(STANDARDS), index=0)
    q_spez = st.number_input("spez. Heizlast W/m²", 10, 200, STANDARDS[std])
    te = st.number_input("Normaußentemperatur °C", -25, 0, -12)
    vl = st.number_input("Vorlauftemperatur °C", 25, 55, 35)
    spreizung = st.number_input("Spreizung K", 3, 10, 5)
    r_belag = st.number_input("Bodenbelag R_λ,B m²K/W", 0.0, 0.30, 0.05, 0.01,
                              help="Fliesen ≈ 0,01 · Parkett ≈ 0,10 · Teppich ≈ 0,15")
    nutz = st.slider("Belegungsfaktor (ohne Möbel/Randzonen)", 0.5, 1.0, 0.85, 0.05)
    zuleitung = st.number_input("Zuleitung je Raum (Hin+Rück) m", 0, 40, 8)
    max_len = st.number_input("max. Heizkreislänge m (16×2)", 60, 150, 100)
    params = dict(q_spez=q_spez, te=te, vl=vl, spreizung=spreizung, r_belag=r_belag,
                  nutz=nutz, zuleitung=zuleitung, max_len=max_len)

dateien = st.file_uploader("Pläne / Raumlisten (Excel, CSV, PDF)",
                           type=["xlsx", "xls", "csv", "pdf"], accept_multiple_files=True)

ocr = st.checkbox("OCR für gescannte PDFs aktivieren (langsamer, benötigt Tesseract)")

teile = []
for d in dateien or []:
    try:
        if d.name.lower().endswith(".pdf"):
            df, info = lese_pdf(d, ocr)
        else:
            df, info = lese_tabelle(d), "Tabelle"
    except Exception as e:  # noqa: BLE001
        st.warning(f"{d.name}: konnte nicht gelesen werden ({e})")
        continue
    if df.empty:
        st.warning(f"{d.name}: keine Räume/Flächen erkannt "
                   "(gescannte PDFs brauchen OCR).")
    else:
        st.caption(f"✅ {d.name}: {len(df)} Räume erkannt über {info}")
        df.insert(0, "Quelle", d.name)
        teile.append(df)

if not teile:
    if st.button("Demo-Daten laden"):
        st.session_state["demo"] = True
    if st.session_state.get("demo"):
        teile.append(pd.DataFrame({
            "Quelle": "demo", "Geschoss": "EG",
            "Raumnr": ["0.01", "0.02", "0.03", "0.04", "0.05", "0.06", "0.07"],
            "Raum": ["Wohnen/Essen", "Küche", "Diele", "Gäste-WC", "Bad",
                     "Büro", "HWR"],
            "Fläche m²": [38.5, 12.2, 8.4, 2.9, 9.6, 14.1, 6.0]}))

if not teile:
    st.info("Lade eine Datei hoch oder starte mit den Demo-Daten.")
    st.stop()

roh = pd.concat(teile, ignore_index=True)
roh["Typ"] = roh["Raum"].map(erkenne_typ)
roh["Zuschlag %"] = 0

st.subheader("1 · Erkannte Räume (editierbar)")
st.caption("Typ korrigieren, Flächen anpassen, Zeilen löschen. "
           "‚Zuschlag %‘ z. B. für Eckräume / viele Außenwände.")
edit = st.data_editor(
    roh, num_rows="dynamic", use_container_width=True, hide_index=True,
    column_config={
        "Typ": st.column_config.SelectboxColumn(options=list(TYPEN), required=True),
        "Fläche m²": st.column_config.NumberColumn(format="%.2f", min_value=0.0),
        "Zuschlag %": st.column_config.NumberColumn(min_value=-50, max_value=100),
    })
edit = edit.dropna(subset=["Raum", "Fläche m²"])

erg = berechne(edit, params)
beh = erg[erg["Status"] != "nicht beheizt"]

st.subheader("2 · Ergebnis")
c = st.columns(5)
c[0].metric("Fläche gesamt", f"{erg['Fläche m²'].sum():.1f} m²")
c[1].metric("beheizt", f"{beh['Fläche m²'].sum():.1f} m²")
c[2].metric("Heizlast", f"{beh['Heizlast W'].sum() / 1000:.1f} kW")
c[3].metric("Heizkreise", int(beh["Heizkreise"].sum()))
c[4].metric("Rohr gesamt", f"{beh['Rohrlänge m'].sum():,.0f} m".replace(",", "."))

if (beh["Status"] != "OK").any():
    st.warning("Einige Räume sind mit den gewählten Parametern nicht deckbar – "
               "Vorlauftemperatur erhöhen, Belag ändern oder Zusatzheizung vorsehen.")

st.dataframe(erg, use_container_width=True, hide_index=True)

g1, g2 = st.columns(2)
if not beh.empty:
    beh = beh.assign(Label=beh["Raumnr"].astype(str) + " " + beh["Raum"])
    g1.plotly_chart(px.bar(beh, x="Label", y="Heizlast W", color="Status",
                           title="Heizlast je Raum"), use_container_width=True)
    g2.plotly_chart(px.bar(beh, x="Label", y=["q W/m²", "q max W/m²"], barmode="group",
                           title="Erforderliche vs. mögliche Wärmestromdichte"),
                    use_container_width=True)

st.download_button("⬇️ Ergebnis als Excel", excel_bytes(erg), "auslegung.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
