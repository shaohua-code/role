#!/usr/bin/env bash

# Require explicit confirmation flag (destroys all compose volumes).
if [[ " $* " != *" --i-understand "* ]]; then
  echo "[greenfield] refused: pass --i-understand (wipes all compose named volumes)" >&2
  exit 2
fi
# 绿场一键重置：清空数据卷 → 迁移 → 种子 → 启动服务（Linux/macOS/容器内 sh）。
# 警告：会删除 iam-postgres-data 与 iam-oidc-signing-data 卷。
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

[ -f "$ROOT/.env" ] || { echo "[greenfield] 缺少根目录 .env"; exit 1; }

echo "[greenfield] 1/4 down -v"
docker compose down -v

echo "[greenfield] 2/4 alembic upgrade head（0001_greenfield_iam）"
docker compose --profile migrate run --build --rm migrate

echo "[greenfield] 3/4 seed-greenfield"
# docker compose run 的命令参数会整体替换服务 command，因此这里必须写全完整命令再追加开关。
SEED_ARGS="--profile seed run --build --rm seed-greenfield python manage.py seed-greenfield --demo-tenant"
[ "${SKIP_DEMO:-0}" = "1" ] && SEED_ARGS="--profile seed run --build --rm seed-greenfield python manage.py seed-greenfield"
# shellcheck disable=SC2086
docker compose $SEED_ARGS

echo "[greenfield] 4/4 up api console"
docker compose up -d --build api console

echo "[greenfield] 完成。使用 .env 中 IAM_ADMIN_EMAIL / IAM_ADMIN_PASSWORD 登录。"
