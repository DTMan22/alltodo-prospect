#!/usr/bin/env python3
"""
Exporte prospects (JSON de fetch_zefix_lindas.py ou CSV legacy) vers CSV import manuel alltodo.
Applique la blocklist opt-out si fournie.
Usage:
  python3 scripts/export_alltodo_csv.py --in data/prospects_vaud.json --out data/export_alltodo.csv [--optout data/optout.txt]
"""
import argparse, csv, json, os

def load(inp):
    if inp.endswith(".json"):
        with open(inp, encoding="utf-8") as f:
            return json.load(f)
    with open(inp, encoding="utf-8-sig") as f:
        sample = f.read(4096); f.seek(0)
        delim = ";" if sample.count(";") > sample.count(",") else ","
        return list(csv.DictReader(f, delimiter=delim))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", default="data/export_alltodo.csv")
    ap.add_argument("--optout", default=None, help="fichier txt, 1 email par ligne")
    a = ap.parse_args()
    blocked = set()
    if a.optout and os.path.exists(a.optout):
        with open(a.optout, encoding="utf-8") as f:
            blocked = {l.strip().lower() for l in f if "@" in l}
    rows = [r for r in load(a.inp) if (r.get("email") or "").lower() not in blocked]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    fields = ["raison_sociale", "uid_che", "forme_juridique", "canton", "commune",
              "adresse", "telephone", "email", "site_web", "noga_label", "source"]
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";", extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    print(f"OK: {len(rows)} lignes (opt-out exclus: {len(blocked)}) -> {a.out}")
    print("Rappel LCD/nLPD : import manuel dans alltodo, 1er contact ciblé + opt-out systématique.")

if __name__ == "__main__":
    main()
