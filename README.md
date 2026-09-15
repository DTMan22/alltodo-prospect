# alltodo-prospect — mini-Apollo suisse pour alltodo.ch

App **séparée** du repo `alltodo`, 100% isolée (pas de connexion auto).
But : détecter les entreprises suisses à prospecter (artisans, commerces, services) et exporter en CSV pour import manuel dans alltodo.

## MVP (priorité ingestion FOSC/Zefix)

1. Ingestion quotidienne Zefix via LINDAS SPARQL (open data, sans clé) + API Zefix REST (optionnelle, sur demande à `zefix@bj.admin.ch`)
2. Recherche locale par NOGA / canton / commune / forme juridique
3. Export CSV compatible import manuel alltodo + respect nLPD/LCD (opt-out)

## Structure

```
alltodo-prospect/
├── config/noga_targets.json   # codes NOGA ciblés alltodo (artisans, services, commerces)
├── sql/001_schema.sql         # tables prospects, events, optout (Supabase/Postgres isolé)
├── scripts/
│   ├── fetch_zefix_lindas.py  # ingestion open data (stdlib uniquement, sans pip)
│   ├── import_local_csv.py    # migre tes CSV local.ch / emails BCC existants
│   └── export_alltodo_csv.py  # export CSV pour import manuel dans alltodo
├── web/index.html             # UI recherche locale (sans build, 100% statique)
├── data/                      # sorties JSON/CSV (gitignoré)
└── .env.example
```

## Bulk Zefix complet (~793k entités, ~3-5h, reprise auto sur panne)

```bash
# SUR LE SERVEUR (le conteneur doit tourner avec le volume /data) :
sudo docker exec alltodo-prospect python3 /app/scripts/bulk_zefix.py --db /data/prospects.db
# En arrière-plan :
nohup sudo docker exec alltodo-prospect python3 /app/scripts/bulk_zefix.py --db /data/prospects.db > bulk.log 2>&1 &
# Suivi : tail -f bulk.log
# Import d'un fichier d'adresses acheté (business-monitor.ch sauvé en CSV) :
sudo docker exec alltodo-prospect python3 /app/scripts/import_csv_generic.py --db /data/prospects.db --in /tmp/liste.csv --source business-monitor
```
UID dédupliqués (raisons sociales fr/de/it), recherche plein-texte insensible aux accents.

## Démarrage rapide (sans Node, sans pip)

```bash
cd /tmp/opencode/alltodo-prospect

# 1. Ingestion test : 50 entreprises, canton de Vaud
python3 scripts/fetch_zefix_lindas.py --limit 50 --canton Vaud --out data/prospects_vaud.json

# 2. Migrer tes CSV existants (depuis le clone alltodo)
python3 scripts/import_local_csv.py --src /tmp/opencode/alltodo/prospection --out data/prospects_legacy.csv

# 3. Export format alltodo (import manuel)
python3 scripts/export_alltodo_csv.py --in data/prospects_vaud.json --out data/export_alltodo.csv

# 4. UI locale
python3 -m http.server 8080 --directory web
# ouvrir http://localhost:8080 (charge data/export_alltodo.csv converti en JSON)
```

## Créer le repo GitHub (manuel, recommandé)

`gh` n'est pas installé ici, et ton token existant est exposé dans le remote `alltodo` (à rotate). Crée le repo à la main :

1. GitHub > New repository > `DTMan22/alltodo-prospect` (privé)
2. Puis :
```bash
cd /tmp/opencode/alltodo-prospect
git init -b main
git add .
git commit -m "feat: scaffold app prospection isolée (ingestion Zefix/FOSC)"
git remote add origin https://github.com/DTMan22/alltodo-prospect.git
git push -u origin main
```

## Conformité (à respecter dès le jour 1)

- LCD art. 3 al.1 let. o : pas d'envoi de masse sans consentement. 1er contact B2B = ciblé, pertinent, expéditeur identifié + adresse CH, opt-out dans chaque message.
- nLPD : minimisation, source publique licite (Zefix/FOSC, site web), blocklist `optout`, suppression 30j max, hébergement CH.
- Téléphone : respecte `*` annuaire (let. u/v).

Voir `sql/001_schema.sql` (table `optout`) et `config/noga_targets.json`.
