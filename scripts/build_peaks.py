#!/usr/bin/env python3
"""Erzeugt Reisebegleiter/Resources/gipfel-europa.json aus Wikidata.

Berge und Gipfel in Europa mit Koordinaten und Höhe, die in mindestens einer Wikipedia
vorkommen oder mindestens 300 m Prominenz haben. Läuft auf GitHub (Ablauf «Gipfel-Datei»),
weil die App-Entwicklungsumgebung keinen Zugang zu Wikidata hat. Nur Standardbibliothek.

Format: {"version": 1, "erzeugt": "...", "gebiet": [süd, west, nord, ost],
         "gipfel": [[QID, Name, Breite, Länge, Höhe, Prominenz (0 = unbekannt), Anzahl Wikipedias], ...]}
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "Reisebegleiter-Gipfeldatei/1.0 (private iOS-App, GitHub Actions)"
# Europa grob, inkl. Kanaren, Island, Nordkap und Kaukasus-Rand.
SOUTH, WEST, NORTH, EAST = 34, -25, 72, 45
STEP = 5  # Grad pro Feld; bei Zeitüberschreitung wird ein Feld geviertelt.
MIN_PROMINENCE = 300
LANGUAGES = "de,fr,it,rm,es,pt,ca,nb,nn,sv,fi,da,is,pl,cs,sk,sl,hr,bs,sr,ro,bg,el,hu,en,mul"

QUERY = """
SELECT ?item ?label ?lat ?lon ?ele ?prom ?links WHERE {{
  SERVICE wikibase:box {{
    ?item wdt:P625 ?coord .
    bd:serviceParam wikibase:cornerSouthWest "Point({w} {s})"^^geo:wktLiteral .
    bd:serviceParam wikibase:cornerNorthEast "Point({e} {n})"^^geo:wktLiteral .
  }}
  VALUES ?type {{ wd:Q8502 wd:Q207326 }}
  ?item wdt:P31 ?type ; wdt:P2044 ?ele ; wikibase:sitelinks ?links .
  OPTIONAL {{ ?item wdt:P2660 ?prom }}
  FILTER(?links >= 1 || (BOUND(?prom) && ?prom >= {minprom}))
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{langs}". ?item rdfs:label ?label . }}
}}
"""


def run(s, w, n, e):
    query = QUERY.format(s=s, w=w, n=n, e=e, minprom=MIN_PROMINENCE, langs=LANGUAGES)
    data = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    request = urllib.request.Request(ENDPOINT, data=data, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)["results"]["bindings"]


def fetch(s, w, n, e, depth=0, peaks=None):
    """Lädt ein Feld; scheitert es, wird es (bis 3 Mal) geviertelt."""
    for attempt in range(3):
        try:
            rows = run(s, w, n, e)
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as error:
            code = getattr(error, "code", None)
            print(f"  Feld {s},{w},{n},{e}: {error}", file=sys.stderr)
            if code == 429:
                time.sleep(60)
                continue
            if depth < 3:
                hs, hw = (s + n) / 2, (w + e) / 2
                for box in ((s, w, hs, hw), (s, hw, hs, e), (hs, w, n, hw), (hs, hw, n, e)):
                    fetch(*box, depth=depth + 1, peaks=peaks)
                return
            time.sleep(10)
    else:
        raise SystemExit(f"Feld {s},{w},{n},{e} lässt sich nicht laden")

    for row in rows:
        try:
            qid = row["item"]["value"].rsplit("/", 1)[-1]
            name = row["label"]["value"]
            lat = float(row["lat"]["value"])
            lon = float(row["lon"]["value"])
            ele = float(row["ele"]["value"])
            links = int(row["links"]["value"])
            prom = float(row["prom"]["value"]) if "prom" in row else 0
        except (KeyError, ValueError):
            continue
        # Ohne Bezeichnung liefert Wikidata die Kennung zurück; unplausible Höhen weglassen.
        if name == qid or not (0 < ele < 6000):
            continue
        old = peaks.get(qid)
        # Mehrere Höhen- oder Prominenzangaben: jeweils die grösste behalten.
        if old:
            ele = max(ele, old[4])
            prom = max(prom, old[5])
        peaks[qid] = [qid, name, round(lat, 5), round(lon, 5), int(round(ele)), int(round(prom)), links]
    print(f"  Feld {s},{w},{n},{e}: {len(rows)} Zeilen, gesamt {len(peaks)}", file=sys.stderr)
    time.sleep(1)  # Wikidata ist ein Gratisdienst.


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "Reisebegleiter/Resources/gipfel-europa.json"
    peaks = {}
    for s in range(SOUTH, NORTH, STEP):
        for w in range(WEST, EAST, STEP):
            fetch(s, w, s + STEP, w + STEP, peaks=peaks)
    result = {
        "version": 1,
        "erzeugt": datetime.date.today().isoformat(),
        "gebiet": [SOUTH, WEST, NORTH, EAST],
        "gipfel": sorted(peaks.values(), key=lambda p: (-p[4], p[0])),
    }
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, separators=(",", ":"))
        file.write("\n")
    print(f"{len(peaks)} Gipfel gespeichert in {output}", file=sys.stderr)
    if len(peaks) < 5000:
        raise SystemExit("Verdächtig wenige Gipfel, Datei bitte prüfen")


if __name__ == "__main__":
    main()
