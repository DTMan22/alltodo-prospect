#!/usr/bin/env python3
"""
Bulk Zefix via LINDAS SPARQL paginé → SQLite (stdlib uniquement).
- 793k entités, ~2000 lignes / ~9s => ~1h-1h30 le bulk complet.
- Reprise sur panne : checkpoint OFFSET dans data/bulk_checkpoint.json.
- Dédupe par UID (les raisons sociales existent en fr/de/it).
Usage :
  python3 scripts/bulk_zefix.py --db data/prospects.db --limit 20000   # subset test
  python3 scripts/bulk_zefix.py --db data/prospects.db                 # full (~1h30)
  python3 scripts/bulk_zefix.py --db data/prospects.db --reset          # repart de zéro
"""
import argparse, json, os, sqlite3, sys, time, urllib.parse, urllib.request

ENDPOINT = "https://lindas.admin.ch/query"
PAGE = 5000  # ~40s/page avec ORDER BY ; bulk complet 793k ≈ 3-5h (lancer sur VPS)

QUERY_TPL = """
PREFIX schema: <http://schema.org/>
PREFIX admin: <https://schema.ld.admin.ch/>
SELECT ?c ?name ?t ?muni ?street ?loc WHERE {{
  ?c a admin:ZefixOrganisation ; schema:name ?name ; admin:municipality ?mid .
  ?mid schema:name ?muni .
  ?c schema:additionalType ?tid . ?tid schema:name ?t .
  OPTIONAL {{ ?c schema:address ?a . ?a schema:streetAddress ?street ; schema:addressLocality ?loc . }}
}} ORDER BY ?c LIMIT {limit} OFFSET {offset}
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects(
  uid TEXT PRIMARY KEY, raison_sociale TEXT, forme TEXT,
  commune TEXT, adresse TEXT, source TEXT DEFAULT 'zefix');
CREATE VIRTUAL TABLE IF NOT EXISTS prospects_fts USING fts5(
  raison_sociale, commune, content='prospects',
  content_rowid='rowid', tokenize='unicode61 remove_diacritics 1');
CREATE TRIGGER IF NOT EXISTS trg_ai AFTER INSERT ON prospects BEGIN
  INSERT INTO prospects_fts(rowid, raison_sociale, commune)
  VALUES (new.rowid, new.raison_sociale, new.commune); END;
"""

def sparql(offset, limit, retries=4):
    q = QUERY_TPL.format(limit=limit, offset=offset)
    body = urllib.parse.urlencode({"query": q, "format": "application/sparql-results+json"}).encode()
    for i in range(retries):
        try:
            req = urllib.request.Request(ENDPOINT, data=body, headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/sparql-results+json",
                "User-Agent": "alltodo-prospect/0.1"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:
            wait = 10 * (2 ** i)
            print(f"  [retry {i+1}] {e} -> pause {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError("SPARQL injoignable après retries")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/prospects.db")
    ap.add_argument("--limit", type=int, default=0, help="0 = tout")
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.db) or ".", exist_ok=True)
    ckpt_path = os.path.join(os.path.dirname(a.db) or ".", "bulk_checkpoint.json")
    offset = 0
    if a.reset and os.path.exists(a.db):
        os.remove(a.db)
    elif os.path.exists(ckpt_path):
        offset = json.load(open(ckpt_path)).get("offset", 0)
        print(f"reprise à OFFSET {offset}")

    con = sqlite3.connect(a.db)
    con.executescript(SCHEMA)
    seen = {r[0] for r in con.execute("SELECT uid FROM prospects")}
    print(f"déjà en base : {len(seen)}")

    total_new, t0 = 0, time.time()
    while True:
        if a.limit and offset >= a.limit:
            break
        raw = sparql(offset, PAGE)
        rows = raw.get("results", {}).get("bindings", [])
        if not rows:
            break
        batch = []
        for b in rows:
            g = lambda k: b.get(k, {}).get("value", "")
            uid = g("c").rsplit("/", 1)[-1]
            if uid in seen:
                continue
            seen.add(uid)
            addr = f"{g('street')}, {g('loc')}".strip(", ") if g("street") else g("loc")
            batch.append((uid, g("name"), g("t"), g("muni"), addr))
        con.executemany(
            "INSERT OR IGNORE INTO prospects(uid,raison_sociale,forme,commune,adresse) VALUES(?,?,?,?,?)",
            batch)
        con.commit()
        total_new += len(batch)
        offset += PAGE
        json.dump({"offset": offset}, open(ckpt_path, "w"))
        el = time.time() - t0
        print(f"offset {offset} : +{len(batch)} nouveaux (total base {len(seen)}, {el:.0f}s)", flush=True)
        time.sleep(0.5)  # politesse
    con.close()
    if (not a.limit) and os.path.exists(ckpt_path):
        os.remove(ckpt_path)
    print(f"TERMINE : +{total_new} nouveaux en {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
