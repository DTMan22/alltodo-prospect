#!/usr/bin/env python3
"""
API recherche prospects (stdlib uniquement).
  python3 api.py --db data/prospects.db --port 8000
Endpoints :
  GET /api/stats                              -> {total, sources:[...]}
  GET /api/search?q=boulanger&commune=&source=&limit=50&offset=0
Recherche FTS5 (insensible accents) avec repli LIKE.
"""
import argparse, json, sqlite3, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB = ""

def qdb(sql, args=()):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()

def fts_query(q):
    # "boulangerie lausanne" -> '"boulangerie"* "lausanne"*'
    toks = [t for t in q.split() if t]
    if not toks:
        return None
    return " ".join('"' + t.replace('"', "") + '"*' for t in toks)

class H(BaseHTTPRequestHandler):
    def send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        p = urllib.parse.parse_qs(u.query)
        g = lambda k, d="": p.get(k, [d])[0]
        try:
            if u.path == "/api/stats":
                total = qdb("SELECT COUNT(*) n FROM prospects")[0]["n"]
                src = qdb("SELECT source, COUNT(*) n FROM prospects GROUP BY source ORDER BY n DESC")
                cant = qdb("SELECT canton, COUNT(*) n FROM prospects WHERE canton<>'' GROUP BY canton ORDER BY n DESC")
                return self.send({"total": total, "sources": src, "cantons": cant})
            if u.path == "/api/search":
                q, commune, source = g("q"), g("commune"), g("source")
                canton = g("canton").upper()
                # raccourci : "VD" seul = filtre canton
                if not canton and len(q.strip()) == 2 and q.strip().isalpha():
                    canton, q = q.strip().upper(), ""
                lim = min(int(g("limit", "50") or 50), 200)
                off = int(g("offset", "0") or 0)
                if not q and not commune and not source and not canton:
                    # pas de critère = pas de lignes (économise mémoire/réseau) ;
                    # le total reste dispo via /api/stats
                    total = qdb("SELECT COUNT(*) n FROM prospects")[0]["n"]
                    return self.send({"rows": [], "total": total, "limit": lim, "offset": off})
                where, args = [], []
                if commune:
                    where.append("commune LIKE ?"); args.append(f"%{commune}%")
                if source:
                    where.append("source LIKE ?"); args.append(f"{source}%")
                if canton:
                    where.append("canton = ?"); args.append(canton)
                if q:
                    m = fts_query(q)
                    try:
                        ids = [r["rowid"] for r in qdb(
                            "SELECT rowid FROM prospects_fts WHERE prospects_fts MATCH ?",
                            (m,))] if m else []
                        if not ids:
                            raise ValueError("vide")
                        where.append(f"prospects.rowid IN ({','.join('?'*len(ids))})")
                        args += ids
                    except Exception:
                        where.append("(raison_sociale LIKE ? OR commune LIKE ?)")
                        args += [f"%{q}%", f"%{q}%"]
                w = ("WHERE " + " AND ".join(where)) if where else ""
                rows = qdb(f"SELECT uid,raison_sociale,forme,commune,adresse,source,"
                           f"telephone,email,site_web,noga,canton,uid_che,description "
                           f"FROM prospects {w} ORDER BY raison_sociale LIMIT ? OFFSET ?",
                           tuple(args) + (lim, off))
                return self.send({"rows": rows, "limit": lim, "offset": off})
            return self.send({"erreur": "route inconnue"}, 404)
        except Exception as e:
            return self.send({"erreur": str(e)}, 500)

    def log_message(self, *a):
        pass

def main():
    global DB
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/prospects.db")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    DB = a.db
    print(f"API prospects sur :{a.port} (db={DB})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()

if __name__ == "__main__":
    main()
