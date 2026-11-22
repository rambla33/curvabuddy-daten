#!/usr/bin/env python3
"""Trägt eine Datei in daten.json (Verzeichnis der Dateien im Release «daten») ein.

Aufruf: manifest.py daten.json <Datei> [<Datei> ...]
Legt daten.json an, falls sie fehlt. Eintrag: Stand (Datum, UTC), SHA-256 und Grösse in Bytes.
Die App prüft damit täglich, ob es etwas Neues gibt, und kontrolliert die Datei nach dem Laden.
"""
import hashlib, json, os, sys, datetime

manifest_path, files = sys.argv[1], sys.argv[2:]
try:
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    manifest = {}
entries = manifest.setdefault("dateien", {})
for path in files:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            sha.update(block)
    entries[os.path.basename(path)] = {
        "stand": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "sha256": sha.hexdigest(),
        "bytes": os.path.getsize(path),
    }
manifest["version"] = 1
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=True)
