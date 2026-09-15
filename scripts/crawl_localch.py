#!/usr/bin/env python3
"""
Crawl local.ch élargi (toute la Suisse) avec reprise sur panne.
Politesse : 3.5s entre requêtes + backoff exponentiel sur 429/403.
Sortie : CSV append (importable via import_csv_generic.py).

Usage :
  python3 scripts/crawl_localch.py --out data/localch_ch.csv --max-pairs 4   # test
  nohup python3 scripts/crawl_localch.py --out data/localch_ch.csv > crawl.log 2>&1 &
  # puis : python3 scripts/import_csv_generic.py --db /data/prospects.db --in data/localch_ch.csv --source localch
"""
import argparse, csv, html as htmllib, os, re, codecs, time
import urllib.request, urllib.error

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# Artisans & services (cible alltodo)
METIERS_SERVICES = {
    "montage-de-meubles": "artisan", "menuiserie": "artisan", "bricolage": "artisan",
    "installateur": "artisan", "maintenance": "artisan", "aide-a-domicile": "service",
    "nettoyage": "service", "demenagement": "service", "peintre": "artisan",
    "plombier": "artisan", "electricien": "artisan", "jardinier": "artisan",
    "reparation": "artisan", "serrurier": "artisan", "chauffage": "artisan",
    "coiffure": "service", "restaurant": "commerce", "boulangerie": "commerce",
    "boucherie": "commerce", "epicerie": "commerce", "fleuriste": "commerce",
    "pharmacie": "commerce", "medecin": "sante", "dentiste": "sante",
    "garage": "auto", "informatique": "tech", "comptable": "pro",
    "avocat": "pro", "immobilier": "pro", "assurance": "pro",
}
# ~40 villes : Romandie (priorité alltodo) + grandes villes CH
VILLES = ["geneve", "lausanne", "nyon", "morges", "fribourg", "neuchatel", "sion",
          "vevey", "montreux", "yverdon-les-bains", "martigny", "sierre", "bulle",
          "la-chaux-de-fonds", "delemont", "payerne", "aigle", "monthey",
          "zurich", "winterthur", "berne", "bienne", "thoune", "bale", "lucerne",
          "st-gall", "lugano", "bellinzone", "locarno", "coire", "schaffhouse",
          "frauenfeld", "aarau", "soleure", "zoug", "schwyz", "altdorf",
          "herisau", "glaris", "fribourg"]

FIELDS = ["raison_sociale", "commune", "adresse", "telephone", "email",
          "site_web", "noga", "source"]

def fix_utf8(s):
    try:
        return htmllib.unescape(s).encode("latin-1", "ignore").decode("utf-8", "ignore")
    except Exception:
        return htmllib.unescape(s)

def fetch(url, retries=5):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr-CH,fr;q=0.9,de-CH;q=0.8"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code in (429, 403) and attempt < retries - 1:
                wait = 20 * (2 ** attempt)
                print(f"    [{e.code}] backoff {wait}s...", flush=True)
                time.sleep(wait)
                continue
            raise
        except Exception:
            if attempt < retries - 1:
                time.sleep(8)
                continue
            raise

def decode_flight(html_text):
    encs = re.findall(r'<script>self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html_text, re.S)
    out = ""
    for e in encs:
        try:
            out += codecs.decode(e, "unicode_escape")
        except Exception:
            pass
    return out

def parse_full(full, noga):
    results = []
    parts = re.split(r'"urlParts":\{', full)
    for seg in parts[1:]:
        up_end = seg.find('}')
        if up_end < 0:
            continue
        seg = seg[up_end:]
        t = re.search(r'"title":"([^"]*)"', seg)
        title = fix_utf8(t.group(1)) if t else ""
        if not title:
            continue
        emails = {e for e in re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', seg)
                  if "local.ch" not in e and "localsearch" not in e}
        tels = set(re.findall(r'\+41[0-9]{9}', seg))
        a = re.search(r'"streetLine":"([^"]*)"[^}]*"city":"([^"]*)"', seg)
        addr, city = "", ""
        if a:
            addr = fix_utf8(a.group(1))
            city = fix_utf8(a.group(2))
        results.append({"raison_sociale": title, "commune": city,
                        "adresse": addr, "telephone": ";".join(sorted(tels)[:2]),
                        "email": ";".join(sorted(emails)[:2]), "site_web": "",
                        "noga": noga, "source": "localch"})
    return results

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/localch_ch.csv")
    ap.add_argument("--max-pairs", type=int, default=0, help="0 = tout")
    a = ap.parse_args()

    pairs = [(m, v) for m in METIERS_SERVICES for v in VILLES]
    done_path = a.out + ".done"
    done = set(open(done_path).read().split()) if os.path.exists(done_path) else set()
    new_file = not os.path.exists(a.out)
    f = open(a.out, "a", newline="", encoding="utf-8-sig")
    w = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";")
    if new_file:
        w.writeheader()

    n_pairs, n_rows, t0 = 0, 0, time.time()
    try:
        for slug, ville in pairs:
            key = f"{slug}/{ville}"
            if key in done:
                continue
            if a.max_pairs and n_pairs >= a.max_pairs:
                break
            try:
                page = fetch(f"https://www.local.ch/fr/q/{slug}/{ville}")
            except Exception as e:
                print(f"[!] {key} erreur: {e}", flush=True)
                continue
            recs = parse_full(decode_flight(page), METIERS_SERVICES[slug])
            for r in recs:
                w.writerow(r)
            f.flush()
            n_pairs += 1
            n_rows += len(recs)
            open(done_path, "a").write(key + "\n")
            done.add(key)
            print(f"[{n_pairs}] {key} : {len(recs)} ({n_rows} lignes, {time.time()-t0:.0f}s)", flush=True)
            time.sleep(3.5)
    finally:
        f.close()
    print(f"TERMINE : {n_pairs} paires, {n_rows} lignes -> {a.out}")

if __name__ == "__main__":
    main()
