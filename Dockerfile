# alltodo-prospect : UI statique + API recherche (SQLite) dans 1 conteneur.
# Données : /data/prospects.db (volume). Init auto depuis le JSON legacy.
# Bulk Zefix complet : docker exec ... python3 /app/scripts/bulk_zefix.py --db /data/prospects.db
FROM nginx:1.27-alpine
RUN apk add --no-cache python3
COPY web/ /usr/share/nginx/html/
COPY api.py scripts/ /app/
COPY scripts/ /app/scripts/
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
VOLUME /data
EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
