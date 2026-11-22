#!/usr/bin/env python3
"""Erzeugt Reisebegleiter/Resources/tankstellen-europa.json aus OpenStreetMap (Overpass).

Alle Tankstellen der Alpenländer (amenity=fuel), damit «Tour vorbereiten» sie ohne Netz und ohne die oft
überlasteten Overpass-Server findet. Läuft auf GitHub (Ablauf «Tankstellen-Datei»), weil die
App-Entwicklungsumgebung keinen Zugang zu Overpass hat. Nur Standardbibliothek.
Aufbau wie scripts/build_passes.py: Felder, die nicht laden, stehen unter «fehlt» und werden beim
nächsten Lauf nachgeladen.

Format: {"version": 1, "erzeugt": "...", "gebiet": [süd, west, nord, ost], "fehlt": [[s, w, n, o], ...],
         "tankstellen": [[OSM-Kennung («n123», «w45»), Marke oder Name, Breite, Länge, Ort], ...]}
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
USER_AGENT = "Reisebegleiter-Tankstellendatei/1.0 (private iOS-App, GitHub Actions)"
# Alpenländer und Nachbarn (CH, AT, LI, DE-Süd, FR-Ost, IT-Nord, SI): kurzer Lauf, wenig GitHub-Minuten.
SOUTH, WEST, NORTH, EAST = 43, 4, 49, 17
STEP = 2
START = time.monotonic()
DEADLINE = 60 * 60  # Sekunden; der Ablauf darf 75 Minuten laufen.

QUERY = """[out:json][timeout:180][bbox:{s},{w},{n},{e}];
nwr["amenity"="fuel"];
out tags center qt;"""


def run(s, w, n, e):
    data = urllib.parse.urlencode({"data": QUERY.format(s=s, w=w, n=n, e=e)}).encode()
    last = None
    for endpoint in ENDPOINTS:
        request = urllib.request.Request(endpoint, data=data, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.load(response)
            if "runtime error" in result.get("remark", ""):
                raise TimeoutError(result["remark"])
            return result["elements"]
        except (OSError, TimeoutError, json.JSONDecodeError, KeyError) as error:
            print(f"  {endpoint} {s},{w},{n},{e}: {error}", file=sys.stderr)
            last = error
            time.sleep(5)
    raise last


def store(elements, stations):
    for element in elements:
        tags = element.get("tags", {})
        lat = element.get("lat", element.get("center", {}).get("lat"))
        lon = element.get("lon", element.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        # Marke ist fürs Ansagen meist am besten («Agrola», «Shell»), sonst Name oder Betreiber.
        name = tags.get("brand") or tags.get("name") or tags.get("operator") or ""
        place = tags.get("addr:city") or tags.get("addr:place") or ""
        key = element["type"][0] + str(element["id"])
        stations[key] = [key, name, round(lat, 5), round(lon, 5), place]


def fetch(box, stations, split):
    """Lädt ein Feld. Gibt die Felder zurück, die nicht geladen werden konnten (bei split geviertelt)."""
    s, w, n, e = box
    try:
        elements = run(s, w, n, e)
    except Exception as error:  # noqa: BLE001 – Overpass ist oft überlastet, später nochmals
        print(f"  Feld {s},{w},{n},{e} später nochmals ({error})", file=sys.stderr)
        if not split or n - s <= 1.25:
            return [box]
        hs, hw = (s + n) / 2, (w + e) / 2
        return [(s, w, hs, hw), (s, hw, hs, e), (hs, w, n, hw), (hs, hw, n, e)]
    store(elements, stations)
    print(f"  Feld {s},{w},{n},{e}: {len(elements)} Tankstellen, gesamt {len(stations)}", file=sys.stderr)
    time.sleep(2)  # Overpass ist ein Gratisdienst.
    return []


# Kerngebiet (Alpen): Fehlt hier ein Feld, ist die Datei unbrauchbar.
ALPS = (43, 5, 48.5, 17)


def overlaps(box, area):
    return box[0] < area[2] and box[2] > area[0] and box[1] < area[3] and box[3] > area[1]


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "Reisebegleiter/Resources/tankstellen-europa.json"
    stations = {}
    pending = [(s, w, s + STEP, w + STEP) for s in range(SOUTH, NORTH, STEP) for w in range(WEST, EAST, STEP)]
    # Bestehende Datei: Fehlen dort Felder (Overpass war überlastet), nur diese nachladen.
    # Mit VOLL=1 (geplante Erneuerung) alles neu laden; Felder, die dann nicht laden, behalten die alten Daten.
    full = os.environ.get("VOLL") == "1"
    old_rows, old_missing = [], []
    try:
        with open(output, encoding="utf-8") as file:
            old = json.load(file)
        old_rows, old_missing = old["tankstellen"], [tuple(box) for box in old.get("fehlt", [])]
    except (OSError, ValueError, KeyError):
        pass
    if old_missing and not full:
        stations = {p[0]: p for p in old_rows}
        # Nur Felder im aktuellen Gebiet (früher umfasste die Datei ganz Europa).
        pending = [box for box in old_missing if overlaps(box, (SOUTH, WEST, NORTH, EAST))]
        old_rows = []
        print(f"Lade {len(pending)} fehlende Felder nach ({len(stations)} Tankstellen vorhanden)", file=sys.stderr)
    # Bis 6 Runden mit Pause: Overpass erholt sich oft. Gescheiterte Felder werden geviertelt.
    for round_ in range(6):
        if round_ > 0:
            if time.monotonic() - START > DEADLINE:
                break
            print(f"Runde {round_ + 1}: {len(pending)} Felder fehlen, Pause 2 Minuten", file=sys.stderr)
            time.sleep(120)
        missing = []
        for box in pending:
            # Zeitlimit des GitHub-Ablaufs nicht reissen: Rest als fehlend zählen.
            if time.monotonic() - START > DEADLINE:
                missing.append(box)
                continue
            missing += fetch(box, stations, split=True)
        pending = missing
        if not pending:
            break
    # Volle Erneuerung: Für Felder, die nicht geladen werden konnten, die alten Daten behalten.
    # Fehlend bleiben nur Felder, die schon in der alten Datei fehlten.
    if old_rows and pending:
        kept = 0
        for row in old_rows:
            if row[0] not in stations and any(box[0] <= row[2] < box[2] and box[1] <= row[3] < box[3] for box in pending):
                stations[row[0]] = row
                kept += 1
        print(f"{kept} alte Tankstellen in nicht geladenen Feldern behalten", file=sys.stderr)
        pending = [box for box in pending if any(overlaps(box, m) for m in old_missing)]
    result = {
        "version": 1,
        "erzeugt": datetime.date.today().isoformat(),
        "gebiet": [SOUTH, WEST, NORTH, EAST],
        "fehlt": [list(box) for box in pending],
        "tankstellen": sorted(stations.values(), key=lambda p: (p[2], p[3])),
    }
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, separators=(",", ":"))
        file.write("\n")
    print(f"{len(stations)} Tankstellen gespeichert in {output}", file=sys.stderr)
    # Teilergebnis trotzdem speichern (der Ablauf legt es auf den Branch); erneut starten lädt den Rest.
    if pending:
        alps = " (auch in den Alpen)" if any(overlaps(box, ALPS) for box in pending) else ""
        print(f"::warning::{len(pending)} Felder fehlen{alps}, Ablauf nochmals starten: {pending}", file=sys.stderr)
    elif len(stations) < 10000:
        raise SystemExit("Verdächtig wenige Tankstellen, Datei bitte prüfen")


if __name__ == "__main__":
    main()
