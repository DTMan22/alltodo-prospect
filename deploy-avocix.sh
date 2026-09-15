#!/usr/bin/env bash
###############################################################################
# Déploiement alltodo-prospect sur avocix.shopuno.ch (Docker + Traefik)
# À exécuter SUR le serveur (82.165.59.154).
#
# Contexte serveur : Traefik (projet /opt/traefik, réseau traefik-net) tient
# les ports 80/443 et émet les certificats Let's Encrypt automatiquement.
# Le nginx hôte n'est PAS utilisé (ne pas lancer certbot --nginx).
#
# Usage :
#   sudo bash deploy-avocix.sh
###############################################################################
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
DOMAIN="avocix.shopuno.ch"
IMAGE="alltodo-prospect:latest"
CONTAINER="alltodo-prospect"
NETWORK="traefik-net"

echo "== 1/3 build Docker =="
docker build -t "$IMAGE" "$APP_DIR"

echo "== 2/3 (re)lance conteneur sur le réseau Traefik =="
docker rm -f "$CONTAINER" 2>/dev/null || true
docker run -d --name "$CONTAINER" --restart unless-stopped \
  --network "$NETWORK" \
  -v alltodo-prospect-data:/data \
  -p 127.0.0.1:8093:80 \
  --label traefik.enable=true \
  --label "traefik.http.routers.avocix.rule=Host(\`$DOMAIN\`)" \
  --label traefik.http.routers.avocix.entrypoints=websecure \
  --label traefik.http.routers.avocix.tls=true \
  --label traefik.http.routers.avocix.tls.certresolver=le \
  --label traefik.http.services.avocix.loadbalancer.server.port=80 \
  "$IMAGE"
sleep 6

echo "== 3/3 vérifications =="
curl -sf http://127.0.0.1:8093/ > /dev/null && echo "OK conteneur (bypass :8093)"
curl -sk -o /dev/null -w "HTTPS direct: %{http_code}\n" https://"$DOMAIN"/
echo "✅ https://$DOMAIN (certificat Let's Encrypt émis auto par Traefik, ~1 min)"
