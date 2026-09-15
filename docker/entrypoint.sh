#!/bin/sh
# Entrypoint conteneur : API Python + nginx.
# - Initialise /data/prospects.db depuis le JSON legacy embarqué (1er démarrage)
# - Le bulk Zefix complet se lance à part : voir README (plusieurs heures, reprise auto)
set -e
DB="${DB_PATH:-/data/prospects.db}"
if [ ! -f "$DB" ]; then
  echo "[entrypoint] init $DB depuis legacy..."
  mkdir -p /data
  python3 /app/scripts/init_db_from_json.py --db "$DB" --in /usr/share/nginx/html/data/prospects.json
fi
echo "[entrypoint] API :8000 + nginx :80"
python3 /app/api.py --db "$DB" --port 8000 &
exec nginx -g 'daemon off;'
