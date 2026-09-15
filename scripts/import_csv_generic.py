#!/usr/bin/env python3
"""
Import CSV générique → SQLite prospects (stdlib).
Couvre : exports business-monitor.ch (sauvés en CSV depuis Excel),
fichiers local.ch legacy, emails BCC.
Usage :
  python3 scripts/import_csv_generic.py --db data/prospects.db --in mon_fichier.csv --source business-monitor
  python3 scripts/import_csv_generic.py --db data/prospects.db --in emails.txt --source bcc --col-email email
En-têtes reconnus (insensible casse/accents) : raison sociale|name|title,
uid|ide|che, forme|legal, canton, commune|city|ville, adresse|address|street,
tel|phone|telephone, email|mail, site|web|website, noga|branche|activite.
"""
import argparse, csv, hashlib, os, sqlite3, unicodedata

FULL_SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects(
  uid TEXT PRIMARY KEY, raison_sociale TEXT, forme TEXT,
  commune TEXT, adresse TEXT, telephone TEXT, email TEXT,
  site_web TEXT, noga TEXT, source TEXT DEFAULT 'import',
  canton TEXT, uid_che TEXT, description TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS prospects_fts USING fts5(
  raison_sociale, commune, content='prospects',
  content_rowid='rowid', tokenize='unicode61 remove_diacritics 1');
CREATE TRIGGER IF NOT EXISTS trg_ai AFTER INSERT ON prospects BEGIN
  INSERT INTO prospects_fts(rowid, raison_sociale, commune)
  VALUES (new.rowid, new.raison_sociale, new.commune); END;
"""
MIGRATE = ["telephone TEXT", "email TEXT", "site_web TEXT", "noga TEXT",
           "canton TEXT", "uid_che TEXT", "description TEXT"]
CANON = {
    "raisonsociale": "raison_sociale", "name": "raison_sociale", "title": "raison_sociale",
    "denomination": "raison_sociale", "company": "raison_sociale",
    "uid": "uid", "ide": "uid", "che": "uid", "companynumber": "uid",
    "forme": "forme", "legalform": "forme", "formelegale": "forme", "rechtsform": "forme",
    "canton": "canton", "commune": "commune", "city": "commune", "ville": "commune",
    "municipality": "commune", "localite": "commune", "ort": "commune",
    "adresse": "adresse", "address": "adresse", "street": "adresse", "rue": "adresse",
    "telephone": "telephone", "tel": "telephone", "phone": "telephone", "telefon": "telephone",
    "email": "email", "mail": "email",
    "siteweb": "site_web", "web": "site_web", "website": "site_web", "url": "site_web",
    "noga": "noga", "branche": "noga", "activite": "noga", "nace": "noga",
}
# colonne canton pas en base bulk : on la concatène dans commune si présente ("VD" seul inutile) -> ignorée sauf adresse
EXTRA = {"canton"}

def norm(s):
    s = unicodedata.normalize("NFKD", (s or "")).encode("ascii", "ignore").decode()
    return "".join(c for c in s.lower() if c.isalnum())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--source", default="import")
    a = ap.parse_args()

    with open(a.inp, encoding="utf-8-sig") as f:
        raw = [l for l in [l.strip() for l in f] if l]
    if not raw:
        print("fichier vide"); return
    if len(raw) == 1 or ("@" in raw[0] and "," not in raw[0] and ";" not in raw[0]):
        rows, header = [{( "email"): l.strip().lower().strip(",;")} for l in raw
                         if "@" in l], ["email"]
        delim = None
    else:
        delim = ";" if raw[0].count(";") >= raw[0].count(",") else ","
        rows = list(csv.DictReader(raw, delimiter=delim))
        header = list(rows[0].keys())
    cmap = {h: CANON.get(norm(h)) for h in header}
    if not any(cmap.values()):
        print("en-têtes non reconnus:", header[:10]); return

    con = sqlite3.connect(a.db)
    con.executescript(FULL_SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(prospects)")}
    for coldef in MIGRATE:
        if coldef.split()[0] not in cols:
            con.execute(f"ALTER TABLE prospects ADD COLUMN {coldef}")
    con.execute("ALTER TABLE prospects ADD COLUMN canton TEXT") if "canton" not in {
        r[1] for r in con.execute("PRAGMA table_info(prospects)")} else None

    n = 0
    for r in rows:
        rec = {"source": a.source}
        for h, v in r.items():
            c = cmap.get(h)
            if c and (v or "").strip():
                rec[c] = v.strip()
        name, mail = rec.get("raison_sociale", ""), rec.get("email", "")
        if not name and not mail:
            continue
        uid = rec.get("uid") or hashlib.md5(
            ((mail or name) + "|" + rec.get("commune", "")).lower().encode()).hexdigest()[:16]
        try:
            con.execute(
                "INSERT OR IGNORE INTO prospects(uid,raison_sociale,forme,commune,adresse,"
                "telephone,email,site_web,noga,canton,source) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (uid, rec.get("raison_sociale", ""), rec.get("forme", ""), rec.get("commune", ""),
                 rec.get("adresse", ""), (rec.get("telephone", "") or "").split(";")[0],
                 (mail or "").split(";")[0].lower(), rec.get("site_web", ""),
                 rec.get("noga", ""), rec.get("canton", ""), a.source))
            n += con.total_changes and 1 or 0
        except sqlite3.IntegrityError:
            pass
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
    con.close()
    print(f"OK: import {a.inp} (source={a.source}) -> base totale {total}")

if __name__ == "__main__":
    main()
