#!/usr/bin/env python3
"""Erzeugt Reisebegleiter/Resources/paesse-europa.json aus OpenStreetMap (Overpass).

Strassenpässe in Europa: benannte Punkte mit mountain_pass=yes, die auf einer befahrbaren Strasse
liegen (trunk bis unclassified). So fallen Wanderpässe weg. Läuft auf GitHub (Ablauf «Pass-Datei»),
weil die App-Entwicklungsumgebung keinen Zugang zu Overpass hat. Nur Standardbibliothek.

Format: {"version": 1, "erzeugt": "...", "gebiet": [süd, west, nord, ost],
         "paesse": [[OSM-Kennung, Name, Breite, Länge, Höhe (0 = unbekannt)], ...]}
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
USER_AGENT = "Reisebegleiter-Passdatei/1.0 (private iOS-App, GitHub Actions)"
SOUTH, WEST, NORTH, EAST = 34, -25, 72, 45
STEP = 5
START = time.monotonic()
DEADLINE = 100 * 60  # Sekunden; der Ablauf darf 120 Minuten laufen.

QUERY = """[out:json][timeout:180][bbox:{s},{w},{n},{e}];
node["mountain_pass"="yes"]["name"]->.p;
way(bn.p)["highway"~"^(trunk|primary|secondary|tertiary|unclassified)(_link)?$"];
node.p(w);
out qt;"""


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


def number(text):
    digits = ""
    for char in (text or "").replace(",", "."):
        if char.isdigit() or (char == "." and "." not in digits):
            digits += char
        elif digits:
            break
    try:
        return int(round(float(digits)))
    except ValueError:
        return 0


def store(elements, passes):
    for element in elements:
        tags = element.get("tags", {})
        name = tags.get("name:de") or tags.get("name")
        if not name or "lat" not in element:
            continue
        ele = number(tags.get("ele"))
        if ele > 5000:
            ele = 0
        passes[element["id"]] = [element["id"], name, round(element["lat"], 5), round(element["lon"], 5), ele]


def fetch(box, passes, split):
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
    store(elements, passes)
    print(f"  Feld {s},{w},{n},{e}: {len(elements)} Pässe, gesamt {len(passes)}", file=sys.stderr)
    time.sleep(2)  # Overpass ist ein Gratisdienst.
    return []


# Kerngebiet (Alpen): Fehlt hier ein Feld, ist die Datei unbrauchbar.
ALPS = (43, 5, 48.5, 17)


def overlaps(box, area):
    return box[0] < area[2] and box[2] > area[0] and box[1] < area[3] and box[3] > area[1]


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "Reisebegleiter/Resources/paesse-europa.json"
    passes = {}
    pending = [(s, w, s + STEP, w + STEP) for s in range(SOUTH, NORTH, STEP) for w in range(WEST, EAST, STEP)]
    # Bestehende Datei: Fehlen dort Felder (Overpass war überlastet), nur diese nachladen.
    # Mit VOLL=1 (geplante Erneuerung) alles neu laden; Felder, die dann nicht laden, behalten die alten Daten.
    full = os.environ.get("VOLL") == "1"
    old_rows, old_missing = [], []
    try:
        with open(output, encoding="utf-8") as file:
            old = json.load(file)
        old_rows, old_missing = old["paesse"], [tuple(box) for box in old.get("fehlt", [])]
    except (OSError, ValueError, KeyError):
        pass
    if old_missing and not full:
        passes = {p[0]: p for p in old_rows}
        pending = old_missing
        old_rows = []
        print(f"Lade {len(pending)} fehlende Felder nach ({len(passes)} Pässe vorhanden)", file=sys.stderr)
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
            missing += fetch(box, passes, split=True)
        pending = missing
        if not pending:
            break
    # Volle Erneuerung: Für Felder, die nicht geladen werden konnten, die alten Daten behalten.
    # Fehlend bleiben nur Felder, die schon in der alten Datei fehlten.
    if old_rows and pending:
        kept = 0
        for row in old_rows:
            if row[0] not in passes and any(box[0] <= row[2] < box[2] and box[1] <= row[3] < box[3] for box in pending):
                passes[row[0]] = row
                kept += 1
        print(f"{kept} alte Pässe in nicht geladenen Feldern behalten", file=sys.stderr)
        pending = [box for box in pending if any(overlaps(box, m) for m in old_missing)]
    result = {
        "version": 1,
        "erzeugt": datetime.date.today().isoformat(),
        "gebiet": [SOUTH, WEST, NORTH, EAST],
        "fehlt": [list(box) for box in pending],
        "paesse": sorted(passes.values(), key=lambda p: (-p[4], p[0])),
    }
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, separators=(",", ":"))
        file.write("\n")
    print(f"{len(passes)} Pässe gespeichert in {output}", file=sys.stderr)
    # Teilergebnis trotzdem speichern (der Ablauf legt es auf den Branch); erneut starten lädt den Rest.
    if pending:
        alps = " (auch in den Alpen)" if any(overlaps(box, ALPS) for box in pending) else ""
        print(f"::warning::{len(pending)} Felder fehlen{alps}, Ablauf nochmals starten: {pending}", file=sys.stderr)
    elif len(passes) < 500:
        raise SystemExit("Verdächtig wenige Pässe, Datei bitte prüfen")


if __name__ == "__main__":
    main()
