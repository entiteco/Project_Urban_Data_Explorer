"""
Fige les données Gold servies par l'API Flask en fichiers JSON statiques et
assemble un dashboard autonome (sans backend) dans static_export/.

Usage (API lancée via docker compose) :
    python3 export_static_data.py [--api http://localhost:5000/api] [--key APIKEY-ADMIN-12345]

Le dossier static_export/ peut ensuite être copié tel quel dans public/ d'Astro.
"""
import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "dashboard-frontend"
OUT = ROOT / "static_export"

# Doit rester synchronisé avec STATIC_FILES dans dashboard-frontend/js/app.js
ENDPOINTS = {
    "get-land-value": "land_value.json",
    "get-social-housing": "social_housing.json",
    "get-tree": "trees.json",
    "get-tree-number": "trees_count.json",
    "get-toilet-by-a": "toilets.json",
    "get-number-station": "stations.json",
    "get-type-ratio-station": "stations_by_type.json",
    "get-stations-points": "stations_points.json",
}

STATIC_CONFIG = '<script>window.URBAN_DATA_CONFIG = { mode: "static", dataPath: "data" };</script>\n    '


def fetch_json(url, api_key):
    req = urllib.request.Request(url, headers={"X-API-KEY": api_key})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:5000/api")
    parser.add_argument("--key", default="APIKEY-ADMIN-12345")
    args = parser.parse_args()

    data_dir = OUT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    errors = 0
    for endpoint, filename in ENDPOINTS.items():
        url = f"{args.api}/{endpoint}"
        try:
            payload = fetch_json(url, args.key)
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            print(f"ERREUR {url} : {e}", file=sys.stderr)
            errors += 1
            continue
        rows = payload.get("data", []) if isinstance(payload, dict) else payload
        if not rows:
            print(f"ERREUR {url} : réponse vide", file=sys.stderr)
            errors += 1
            continue
        target = data_dir / filename
        # JSON compact : même structure que la réponse API ({"data": [...]})
        target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"OK  {endpoint:<24} -> {target.relative_to(ROOT)}  ({len(rows)} lignes, {target.stat().st_size / 1024:.0f} Ko)")

    if errors:
        print(f"{errors} endpoint(s) en échec, export incomplet.", file=sys.stderr)
        sys.exit(1)

    # Fond géographique + front (index.html configuré en mode statique)
    shutil.copy(FRONTEND / "data" / "arrondissements.geojson", data_dir / "arrondissements.geojson")
    shutil.copytree(FRONTEND / "css", OUT / "css", dirs_exist_ok=True)
    shutil.copytree(FRONTEND / "js", OUT / "js", dirs_exist_ok=True)
    (OUT / "js" / "main.js").unlink(missing_ok=True)

    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    marker = '<script src="js/app.js'
    assert marker in html, "balise app.js introuvable dans index.html"
    html = html.replace(marker, STATIC_CONFIG + marker, 1)
    (OUT / "index.html").write_text(html, encoding="utf-8")

    print(f"Dashboard statique prêt dans {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
