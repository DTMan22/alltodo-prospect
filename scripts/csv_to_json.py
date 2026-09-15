#!/usr/bin/env python3
"""
Convertit un CSV prospects (séparateur ; ou ,) en JSON pour l'UI web.
Usage:
  python3 scripts/csv_to_json.py --in data/prospects_legacy.csv --out web/data/prospects.json [--max 0]
  --max 0 = tout (défaut). Mettre 2000 pour un échantillon.
"""
import argparse, csv, json, os

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=0)
    a = ap.parse_args()
    with open(a.inp, encoding="utf-8-sig") as f:
        sample = f.read(8192); f.seek(0)
        delim = ";" if sample.count(";") > sample.count(",") else ","
        rows = list(csv.DictReader(f, delimiter=delim))
    if a.max > 0:
        rows = rows[:a.max]
    # ne garde que les lignes avec au moins un nom ou un email
    rows = [r for r in rows if (r.get("raison_sociale") or "").strip() or (r.get("email") or "").strip()]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    print(f"OK: {len(rows)} prospects -> {a.out}")

if __name__ == "__main__":
    main()
