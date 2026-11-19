#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $EUID -ne 0 ]]; then
  echo 'Run as root on the approved IAM deployment host.' >&2
  exit 1
fi

phase=${1:-}
release_tag=${2:-}
if [[ $phase != prepare && $phase != activate ]] || [[ ! $release_tag =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Usage: first-release.sh prepare <40-char-sha> | activate <40-char-sha> <offsite-backup-sha256>' >&2
  exit 1
fi

exec 9>/run/lock/iam-deploy.lock
flock -n 9 || { echo 'Another IAM deployment is in progress.' >&2; exit 1; }

iam_root=/opt/iam
shared_dir=$iam_root/shared
incoming_dir=/home/iamdeploy/incoming/$release_tag
release_dir=$iam_root/releases/$release_tag
env_file=$shared_dir/.env.production.local
backup_dir=$shared_dir/backups
backup_file=$backup_dir/iam-preinit-$release_tag.dump
restore_marker=$backup_file.restore-ok

if [[ -e $shared_dir/initialized || -e $shared_dir/current-tag || ! -f $env_file ]]; then
  echo 'First release requires a prepared, uninitialized IAM host.' >&2
  exit 1
fi

export IAM_RELEASE_TAG=$release_tag
compose=(docker compose -f "$release_dir/compose.production.yaml"
  -f "$release_dir/compose.production.host-nginx.yaml" --env-file "$env_file")

if [[ $phase == prepare ]]; then
  if [[ ! -f $incoming_dir/images.tar.gz || ! -f $incoming_dir/source.tar.gz || -e $backup_file ]]; then
    echo 'Release bundle is missing or the initial backup already exists.' >&2
    exit 1
  fi
  while IFS= read -r archive_path; do
    case "$archive_path" in
      /*|../*|*/../*|*/..) echo 'Unsafe release archive path.' >&2; exit 1 ;;
    esac
  done < <(tar -tzf "$incoming_dir/source.tar.gz")
  install -d -m 0755 "$release_dir"
  tar -xzf "$incoming_dir/source.tar.gz" --no-same-owner -C "$release_dir"
  docker load -i "$incoming_dir/images.tar.gz" >/dev/null
  "${compose[@]}" config --quiet
  "${compose[@]}" up -d --wait --no-deps postgres

  public_tables=$("${compose[@]}" exec -T postgres psql -U iam -d iam -Atc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
  if [[ $public_tables != 0 ]]; then
    echo 'IAM database is not empty. Stop and use the existing-database migration procedure.' >&2
    exit 1
  fi

  install -d -o root -g root -m 0700 "$backup_dir"
  "${compose[@]}" exec -T postgres pg_dump -U iam -Fc iam > "$backup_file"
  chmod 0600 "$backup_file"
  sha256sum "$backup_file" > "$backup_file.sha256"
  chmod 0600 "$backup_file.sha256"

  scratch_db="iam_restore_$(openssl rand -hex 6)"
  "${compose[@]}" exec -T postgres createdb -U iam "$scratch_db"
  cleanup_scratch() { "${compose[@]}" exec -T postgres dropdb -U iam "$scratch_db"; }
  trap cleanup_scratch EXIT
  "${compose[@]}" exec -T postgres pg_restore -U iam -d "$scratch_db" < "$backup_file"
  restored_tables=$("${compose[@]}" exec -T postgres psql -U iam -d "$scratch_db" -Atc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
  if [[ $restored_tables != 0 ]]; then
    echo 'Scratch database did not match the empty pre-migration IAM database.' >&2
    exit 1
  fi
  sha256sum "$backup_file" | awk '{print $1}' > "$restore_marker"
  chmod 0600 "$restore_marker"
  echo "IAM pre-migration backup and isolated restore passed: $backup_file"
  echo 'Copy the dump and .sha256 file to an encrypted, off-host destination before activate.'
  exit 0
fi

offsite_sha256=${3:-}
if [[ ! $offsite_sha256 =~ ^[0-9a-f]{64}$ || ! -f $backup_file || ! -f $restore_marker ]]; then
  echo 'Activation needs a verified off-host backup SHA-256 and completed restore drill.' >&2
  exit 1
fi

if [[ ! -d $release_dir || ! -f $shared_dir/nginx/iam-ip.nginx.conf ||
  -e /etc/nginx/conf.d/iam-ip.conf ]]; then
  echo 'Release files or Nginx candidate are missing, or the IAM site already exists.' >&2
  exit 1
fi
if ! grep -Eq '^IAM_BOOTSTRAP_ADMIN_PASSWORD=.+$' "$env_file"; then
  echo 'One-time bootstrap password is missing from the protected environment file.' >&2
  exit 1
fi
"${compose[@]}" config --quiet

backup_sha256=$(sha256sum "$backup_file" | awk '{print $1}')
if [[ $backup_sha256 != "$offsite_sha256" || $(<"$restore_marker") != "$backup_sha256" ]]; then
  echo 'Backup hash or restore marker does not match.' >&2
  exit 1
fi

public_tables=$("${compose[@]}" exec -T postgres psql -U iam -d iam -Atc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
if [[ $public_tables != 0 ]]; then
  echo 'IAM database changed since the empty-database backup; stop.' >&2
  exit 1
fi

# This is the only first-release phase that writes IAM schema and the bootstrap account.
"${compose[@]}" run --rm --no-deps migrate
"${compose[@]}" --profile bootstrap run --rm --no-deps bootstrap-admin
"${compose[@]}" up -d --no-deps --no-build api console

healthy=false
for _ in {1..30}; do
  if curl --fail --silent --show-error --max-time 3 \
    http://127.0.0.1:18080/api/v1/ready >/dev/null 2>&1; then
    healthy=true
    break
  fi
  sleep 4
done
if [[ $healthy != true ]]; then
  echo 'IAM API is not ready. Do not install the Nginx route or mark the release initialized.' >&2
  exit 1
fi

nginx_site=/etc/nginx/conf.d/iam-ip.conf
install -o root -g root -m 0644 "$shared_dir/nginx/iam-ip.nginx.conf" "$nginx_site"
if ! nginx -t; then
  mv "$nginx_site" "$shared_dir/nginx/iam-ip.failed.conf"
  exit 1
fi
systemctl reload nginx
if ! curl --fail --silent --show-error --noproxy '*' \
  --cacert "$shared_dir/tls/ip.crt" --resolve '175.178.62.55:443:127.0.0.1' \
  https://175.178.62.55/api/v1/ready >/dev/null; then
  echo 'HTTPS IAM readiness failed. Keep initialization marker absent and investigate.' >&2
  exit 1
fi
if ! curl --fail --silent --show-error --noproxy '*' \
  --cacert "$shared_dir/tls/ip.crt" --resolve '175.178.62.55:443:127.0.0.1' \
  https://175.178.62.55/.well-known/openid-configuration >/dev/null; then
  echo 'OIDC discovery failed. Keep initialization marker absent and investigate.' >&2
  exit 1
fi

sed -n 's/^IAM_BOOTSTRAP_ADMIN_PASSWORD=//p' "$env_file" > "$shared_dir/bootstrap-admin-password"
chmod 0600 "$shared_dir/bootstrap-admin-password"
sed -i '/^IAM_BOOTSTRAP_ADMIN_PASSWORD=/d' "$env_file"
printf '%s\n' "$release_tag" > "$shared_dir/current-tag"
chmod 0600 "$shared_dir/current-tag"
printf 'initialized %s\n' "$(date -u +%FT%TZ)" > "$shared_dir/initialized"
chmod 0600 "$shared_dir/initialized"
echo "IAM first release $release_tag is ready. Admin password is in a root-only server file."
