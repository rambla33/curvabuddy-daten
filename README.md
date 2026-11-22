# curvabuddy-daten

Daten-Dateien für die iPhone-App CurvaBuddy. Die App lädt sie von hier, damit neue Daten ohne Neubau der App ankommen.
Alles liegt im Release **daten** (Dateien) und im Ordner `stand/` (Stand der letzten Läufe).

| Datei | Inhalt | Erneuert |
|---|---|---|
| `tankstellen-europa.json` | Tankstellen (OpenStreetMap), Alpenländer | alle 2 Monate (Ablauf «Daten») |
| `gipfel-europa.json` | Gipfel (Wikidata) | jährlich im Februar |
| `paesse-europa.json` | Strassenpässe (OpenStreetMap) | jährlich im März |
| `daten.json` | Verzeichnis mit Stand, SHA-256 und Grösse jeder Datei; die App prüft damit täglich auf Neues | bei jedem Lauf |
| `alpen.pmtiles` | Vektorkarte der Alpen bis Zoomstufe 12 (ca. 500 MB), Gebiet 5.5–15° Ost, 43.5–48.5° Nord | monatlich (Ablauf «Alpenkarte (OSM)») |

Direkter Link: https://github.com/rambla33/curvabuddy-daten/releases/download/daten/alpen.pmtiles

## Herkunft und Lizenz

- Kartendaten: © OpenStreetMap-Mitwirkende, [Open Database License (ODbL)](https://www.openstreetmap.org/copyright).
- Basiskarte: [Protomaps](https://protomaps.com) (täglicher Auszug der OpenStreetMap-Daten), mit dem Werkzeug `pmtiles extract` zugeschnitten.
