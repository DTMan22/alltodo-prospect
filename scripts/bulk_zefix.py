#!/usr/bin/env python3
"""
Bulk Zefix via LINDAS SPARQL → SQLite (stdlib uniquement).
Pagination par CLÉ (FILTER STR(?c) > last) : vitesse constante jusqu'à 793k,
contrairement à OFFSET qui s'écroule. Checkpoint reprise auto.
Dédupe par UID (raisons sociales fr/de/it).

Usage :
  python3 scripts/bulk_zefix.py --db data/prospects.db --limit 6000   # test
  python3 scripts/bulk_zefix.py --db data/prospects.db                 # full
  nohup python3 scripts/bulk_zefix.py --db /data/prospects.db > bulk.log 2>&1 &
"""
import argparse, json, os, sqlite3, time, urllib.parse, urllib.request

ENDPOINT = "https://lindas.admin.ch/query"
PAGE = 5000

QUERY_TPL = """
PREFIX schema: <http://schema.org/>
PREFIX admin: <https://schema.ld.admin.ch/>
SELECT ?c ?name ?t ?muni ?street ?loc WHERE {{
  ?c a admin:ZefixOrganisation ; schema:name ?name ; admin:municipality ?mid .
  ?mid schema:name ?muni .
  ?c schema:additionalType ?tid . ?tid schema:name ?t .
  OPTIONAL {{ ?c schema:address ?a . ?a schema:streetAddress ?street ; schema:addressLocality ?loc . }}
  FILTER(STR(?c) > "{last}")
}} ORDER BY ?c LIMIT {limit}
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects(
  uid TEXT PRIMARY KEY, raison_sociale TEXT, forme TEXT,
  commune TEXT, adresse TEXT, telephone TEXT, email TEXT,
  site_web TEXT, noga TEXT, canton TEXT, source TEXT DEFAULT 'zefix');
CREATE VIRTUAL TABLE IF NOT EXISTS prospects_fts USING fts5(
  raison_sociale, commune, content='prospects',
  content_rowid='rowid', tokenize='unicode61 remove_diacritics 1');
CREATE TRIGGER IF NOT EXISTS trg_ai AFTER INSERT ON prospects BEGIN
  INSERT INTO prospects_fts(rowid, raison_sociale, commune)
  VALUES (new.rowid, new.raison_sociale, new.commune); END;
"""

def sparql(last, limit, retries=4):
    q = QUERY_TPL.format(last=last.replace('"', ""), limit=limit)
    body = urllib.parse.urlencode({"query": q, "format": "application/sparql-results+json"}).encode()
    for i in range(retries):
        try:
            req = urllib.request.Request(ENDPOINT, data=body, headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/sparql-results+json",
                "User-Agent": "alltodo-prospect/0.1"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:
            wait = 10 * (2 ** i)
            print(f"  [retry {i+1}] {e} -> pause {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError("SPARQL injoignable après retries")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/prospects.db")
    ap.add_argument("--limit", type=int, default=0, help="0 = tout (nb max de bindings lus)")
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.db) or ".", exist_ok=True)
    ckpt_path = os.path.join(os.path.dirname(a.db) or ".", "bulk_checkpoint.json")
    last, read = "", 0
    if os.path.exists(ckpt_path):
        try:
            ck = json.load(open(ckpt_path))
            if ck.get("mode") == "keyset":
                last = ck.get("last", "")
                print(f"reprise après {last}")
            else:
                print("ancien checkpoint OFFSET ignoré (reprise par clé depuis le début, dédupe via DB)")
        except Exception:
            pass

    con = sqlite3.connect(a.db)
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(prospects)")}
    for col in ("telephone", "email", "site_web", "noga", "canton"):
        if col not in cols:
            con.execute(f"ALTER TABLE prospects ADD COLUMN {col} TEXT")
    seen = {r[0] for r in con.execute("SELECT uid FROM prospects")}
    print(f"déjà en base : {len(seen)}")

    total_new, t0 = 0, time.time()
    while True:
        if a.limit and read >= a.limit:
            break
        raw = sparql(last, PAGE)
        rows = raw.get("results", {}).get("bindings", [])
        if not rows:
            break
        batch = []
        for b in rows:
            g = lambda k: b.get(k, {}).get("value", "")
            uri = g("c")
            uid = uri.rsplit("/", 1)[-1]
            last = uri  # avance même si déjà vu (clé de pagination)
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
        read += len(rows)
        json.dump({"mode": "keyset", "last": last}, open(ckpt_path, "w"))
        el = time.time() - t0
        print(f"lus {read} : +{len(batch)} nouveaux (base {len(seen)}, {el:.0f}s, {read/max(el,1):.0f} bind/s)", flush=True)
        time.sleep(0.3)
    con.close()
    if not a.limit and os.path.exists(ckpt_path):
        os.remove(ckpt_path)
    print(f"TERMINE : +{total_new} nouveaux en {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
