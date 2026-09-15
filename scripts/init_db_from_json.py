#!/usr/bin/env python3
"""Init SQLite depuis le JSON legacy embarqué (1er démarrage conteneur)."""
import argparse, json, os, sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects(
  uid TEXT PRIMARY KEY, raison_sociale TEXT, forme TEXT,
  commune TEXT, adresse TEXT, telephone TEXT, email TEXT,
  site_web TEXT, noga TEXT, canton TEXT, source TEXT DEFAULT 'legacy');
CREATE VIRTUAL TABLE IF NOT EXISTS prospects_fts USING fts5(
  raison_sociale, commune, content='prospects',
  content_rowid='rowid', tokenize='unicode61 remove_diacritics 1');
CREATE TRIGGER IF NOT EXISTS trg_ai AFTER INSERT ON prospects BEGIN
  INSERT INTO prospects_fts(rowid, raison_sociale, commune)
  VALUES (new.rowid, new.raison_sociale, new.commune); END;
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--in", dest="inp", required=True)
    a = ap.parse_args()
    rows = json.load(open(a.inp, encoding="utf-8"))
    os.makedirs(os.path.dirname(a.db) or ".", exist_ok=True)
    con = sqlite3.connect(a.db)
    con.executescript(SCHEMA)
    import hashlib
    batch = []
    for r in rows:
        mail = (r.get("email") or "").split(";")[0].strip().lower()
        name = (r.get("raison_sociale") or "").strip()
        if not name and not mail:
            continue
        uid = (r.get("uid_che") or "").strip() or hashlib.md5(
            ((mail or name) + "|" + (r.get("commune") or "")).lower().encode()).hexdigest()[:16]
        batch.append((uid, name, r.get("forme_juridique", ""), r.get("commune", ""),
                      r.get("adresse", ""), (r.get("telephone") or "").split(";")[0],
                      mail, r.get("site_web", ""), r.get("noga_label", ""),
                      r.get("canton", ""), r.get("source", "legacy")))
    con.executemany("INSERT OR IGNORE INTO prospects VALUES(?,?,?,?,?,?,?,?,?,?,?)", batch)
    con.commit()
    print(f"init: {con.execute('SELECT COUNT(*) FROM prospects').fetchone()[0]} prospects")
    con.close()

if __name__ == "__main__":
    main()
