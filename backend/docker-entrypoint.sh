#!/bin/sh
set -eu

# 迁移作业只负责升级 schema，成功退出后 API 服务才会启动。
if [ "${IAM_MIGRATE_ONLY:-false}" = "true" ]; then
  exec alembic upgrade head
fi

# 开发保留原有自动迁移/引导；未显式配置时非开发默认不做 schema 或身份写入。
run_migrations=${IAM_RUN_MIGRATIONS:-}
bootstrap_admin=${IAM_BOOTSTRAP_ADMIN:-}
if [ -z "$run_migrations" ]; then
  case "${APP_ENV:-development}" in development) run_migrations=true ;; *) run_migrations=false ;; esac
fi
if [ -z "$bootstrap_admin" ]; then
  case "${APP_ENV:-development}" in development) bootstrap_admin=true ;; *) bootstrap_admin=false ;; esac
fi

if [ "$run_migrations" = "true" ]; then
  alembic upgrade head
fi
if [ "${IAM_ENSURE_OIDC_KEY:-true}" = "true" ]; then
  python manage.py ensure-oidc-key
fi
if [ "$bootstrap_admin" = "true" ]; then
  python manage.py bootstrap-admin
fi

# 显式命令用于一次性运维任务；没有命令时，开发热重载与生产多 worker 启动路径分开。
if [ "$#" -gt 0 ]; then
  exec "$@"
fi
if [ "${APP_ENV:-development}" = "development" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-2}"
