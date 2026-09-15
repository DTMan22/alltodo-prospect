#!/usr/bin/env bash
###############################################################################
# Déploiement alltodo-prospect sur avocix.shopuno.ch (Docker + nginx)
# À exécuter SUR le serveur (82.165.59.154), pas dans ce sandbox.
#
# Usage :
#   sudo bash deploy-avocix.sh
#
# Fait :
#   1. build l'image Docker alltodo-prospect
#   2. (re)lance le conteneur sur 127.0.0.1:8093
#   3. crée le vhost nginx avocix.shopuno.ch en reverse-proxy + TLS
###############################################################################
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
DOMAIN="avocix.shopuno.ch"
PORT="8093"
IMAGE="alltodo-prospect:latest"
CONTAINER="alltodo-prospect"

echo "== 1/4 build Docker =="
docker build -t "$IMAGE" "$APP_DIR"

echo "== 2/4 (re)lance conteneur =="
docker rm -f "$CONTAINER" 2>/dev/null || true
docker run -d --name "$CONTAINER" --restart unless-stopped \
  -p 127.0.0.1:"$PORT":80 "$IMAGE"
sleep 3
curl -sf http://127.0.0.1:"$PORT"/ > /dev/null && echo "OK conteneur répond sur $PORT"

echo "== 3/4 vhost nginx =="
cat > /etc/nginx/sites-available/"$DOMAIN".conf <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/"$DOMAIN".conf /etc/nginx/sites-enabled/"$DOMAIN".conf
nginx -t

echo "== 4/4 TLS + reload =="
if [ ! -d /etc/letsencrypt/live/"$DOMAIN" ]; then
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m contact@alltodo.ch --redirect
else
  echo "Certificat existant, simple reload"
fi
systemctl reload nginx
echo "✅ Déployé : https://$DOMAIN"
curl -s -o /dev/null -w "HTTP %{http_code}\n" https://"$DOMAIN"/
