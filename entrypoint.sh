#!/bin/sh
set -e

# Pričekaj bazu i inicijaliziraj shemu (idempotentno, CREATE IF NOT EXISTS).
echo "[entrypoint] Inicijaliziram shemu (čekam Postgres)..."
i=1
while [ "$i" -le 30 ]; do
  if python /app/collect.py --init 2>/dev/null; then
    echo "[entrypoint] Shema spremna."
    break
  fi
  echo "  ...baza još nije spremna ($i/30)"
  i=$((i + 1))
  sleep 2
done

echo "[entrypoint] Pokrećem supercronic (raspored iz /app/crontab)."
echo "[entrypoint] Prikupljanje ide automatski; analizu pokreni s 'docker compose exec'."
exec supercronic /app/crontab
