#!/usr/bin/env python3
"""
Migre tes CSV legacy (prospection/ de alltodo) vers un CSV unifié prospects.
Usage:
  python3 scripts/import_local_csv.py --src /tmp/opencode/alltodo/prospection --out data/prospects_legacy.csv
Stdlib uniquement.
"""
import argparse, csv, os, glob

FIELD_MAP = ["metier_cible", "title", "category", "address", "phone", "email", "website", "slug", "city", "zip"]

def read_csv(path):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        # détecte ; ou ,
        sample = f.read(4096); f.seek(0)
        delim = ";" if sample.count(";") > sample.count(",") else ","
        for r in csv.DictReader(f, delimiter=delim):
            rows.append(r)
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default="data/prospects_legacy.csv")
    a = ap.parse_args()
    seen, out = set(), []
    for path in sorted(glob.glob(os.path.join(a.src, "contacts_*.csv"))):
        try:
            rows = read_csv(path)
        except Exception as e:
            print(f"skip {path}: {e}")
            continue
        for r in rows:
            email = (r.get("email") or "").strip().lower()
            phone = (r.get("phone") or r.get("telephone") or "").strip()
            name = (r.get("title") or r.get("raison_sociale") or r.get("name") or "").strip()
            key = email or (name + "|" + (r.get("city") or r.get("commune") or ""))
            if not key or key in seen:
                continue
            seen.add(key)
            out.append({
                "raison_sociale": name,
                "commune": r.get("city") or r.get("commune") or "",
                "adresse": r.get("address") or r.get("adresse") or "",
                "telephone": phone.split(";")[0] if phone else "",
                "email": email.split(";")[0] if email else "",
                "site_web": r.get("website") or r.get("site_web") or "",
                "noga_label": r.get("metier_cible") or r.get("category") or "",
                "canton": "", "uid_che": "", "forme_juridique": "",
                "source": "csv_legacy:" + os.path.basename(path),
                "statut": "nouveau",
            })
    # + emails_bcc.csv (1 adresse par ligne)
    bcc = os.path.join(a.src, "emails_bcc.csv")
    if os.path.exists(bcc):
        with open(bcc, encoding="utf-8-sig") as f:
            for line in f:
                e = line.strip().lower().strip(",;")
                if "@" in e and e not in seen:
                    seen.add(e)
                    out.append({"raison_sociale": "", "commune": "", "adresse": "",
                                "telephone": "", "email": e, "site_web": "",
                                "noga_label": "", "canton": "", "uid_che": "",
                                "forme_juridique": "", "source": "csv_legacy:emails_bcc.csv",
                                "statut": "nouveau"})
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    fields = ["raison_sociale", "uid_che", "forme_juridique", "canton", "commune",
              "adresse", "telephone", "email", "site_web", "noga_label", "source", "statut"]
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader(); w.writerows(out)
    print(f"OK: {len(out)} prospects dédupliqués -> {a.out}")

if __name__ == "__main__":
    main()
