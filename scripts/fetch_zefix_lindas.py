#!/usr/bin/env python3
"""
Ingestion Zefix open data via LINDAS SPARQL (sans clé, stdlib uniquement).
Usage:
  python3 scripts/fetch_zefix_lindas.py --limit 50 --canton Vaud --out data/prospects_vaud.json
  python3 scripts/fetch_zefix_lindas.py --limit 200 --out data/prospects.json
"""
import argparse, json, os, sys, urllib.parse, urllib.request

ENDPOINT = "https://lindas.admin.ch/query"

QUERY_TPL = """
PREFIX schema: <http://schema.org/>
PREFIX admin: <https://schema.ld.admin.ch/>
SELECT ?company_uri ?name ?company_type ?municipality ?adresse ?locality WHERE {{
  ?company_uri a admin:ZefixOrganisation ;
     schema:name ?name ;
     admin:municipality ?muni_id .
  ?muni_id schema:name ?municipality .
  ?company_uri schema:additionalType ?type_id .
  ?type_id schema:name ?company_type .
  OPTIONAL {{ ?company_uri schema:address ?adr .
             ?adr schema:streetAddress ?adresse ;
                  schema:addressLocality ?locality . }}
  FILTER(langMatches(lang(?name), "fr") || langMatches(lang(?name), "de"))
  {canton_filter}
  FILTER(CONTAINS(LCASE(?municipality), LCASE("{commune}")) || "{commune}" = "")
}}
LIMIT {limit}
"""

def fetch(limit, commune):
    canton_filter = ""  # LINDAS zefix n'expose pas le canton directement ; on filtre côté commune + enrichissement Zefix REST ensuite
    q = QUERY_TPL.format(limit=int(limit), commune=commune.replace('"', ''), canton_filter=canton_filter)
    body = urllib.parse.urlencode({
        "query": q,
        "format": "application/sparql-results+json",
    }).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/sparql-results+json",
                 "User-Agent": "alltodo-prospect/0.1"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))

def to_prospects(raw, canton_hint):
    out, seen = [], set()
    for b in raw.get("results", {}).get("bindings", []):
        g = lambda k: b.get(k, {}).get("value", "")
        uid = g("company_uri").rsplit("/", 1)[-1]
        if uid in seen:
            continue
        seen.add(uid)
        out.append({
            "uid_che": uid,
            "raison_sociale": g("name"),
            "forme_juridique": g("company_type"),
            "canton": canton_hint,
            "commune": g("municipality"),
            "adresse": f"{g('adresse')}, {g('locality')}".strip(", "),
            "source": "zefix",
            "statut": "nouveau",
        })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", default="50")
    ap.add_argument("--canton", default="", help="Hint canton (ex: Vaud). Filtre serveur = commune uniquement.")
    ap.add_argument("--commune", default="", help="Filtre commune (ex: Yverdon). Vide = tout.")
    ap.add_argument("--out", default="data/prospects.json")
    a = ap.parse_args()
    raw = fetch(a.limit, a.commune)
    prospects = to_prospects(raw, a.canton)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(prospects, f, ensure_ascii=False, indent=2)
    print(f"OK: {len(prospects)} prospects -> {a.out}")

if __name__ == "__main__":
    main()
