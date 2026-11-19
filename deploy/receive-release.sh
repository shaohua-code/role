#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $EUID -ne 0 ]]; then
  echo 'Run through the dedicated iamdeploy sudo rule.' >&2
  exit 1
fi

release_tag=${1:-}
if [[ ! $release_tag =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Expected an immutable 40-character Git commit SHA.' >&2
  exit 1
fi

exec 9>/run/lock/iam-deploy.lock
flock -n 9 || { echo 'Another IAM deployment is in progress.' >&2; exit 1; }

iam_root=/opt/iam
shared_dir=$iam_root/shared
incoming_dir=/home/iamdeploy/incoming/$release_tag
release_dir=$iam_root/releases/$release_tag
env_file=$shared_dir/.env.production.local
current_tag_file=$shared_dir/current-tag

for required_file in "$shared_dir/initialized" "$env_file" "$current_tag_file" \
  "$incoming_dir/images.tar.gz" "$incoming_dir/source.tar.gz"; do
  if [[ ! -f $required_file ]]; then
    echo "Missing deployment prerequisite: $required_file" >&2
    exit 1
  fi
done

current_tag=$(<"$current_tag_file")
if [[ ! $current_tag =~ ^[0-9a-f]{40}$ || ! -d $iam_root/releases/$current_tag ]]; then
  echo 'Current release marker is invalid.' >&2
  exit 1
fi

# Only repository-owned relative paths may be extracted into a release directory.
while IFS= read -r archive_path; do
  case "$archive_path" in
    /*|../*|*/../*|*/..) echo 'Unsafe release archive path.' >&2; exit 1 ;;
  esac
done < <(tar -tzf "$incoming_dir/source.tar.gz")

install -d -m 0755 "$release_dir"
tar -xzf "$incoming_dir/source.tar.gz" --no-same-owner -C "$release_dir"
docker load -i "$incoming_dir/images.tar.gz" >/dev/null

export IAM_RELEASE_TAG=$release_tag
new_compose=(docker compose -f "$release_dir/compose.production.yaml"
  -f "$release_dir/compose.production.host-nginx.yaml" --env-file "$env_file")
"${new_compose[@]}" config --quiet

new_head=$(docker run --rm --network none --entrypoint python "iam-platform-api:$release_tag" -c \
  'from alembic.config import Config; from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config("/app/alembic.ini")).get_current_head())')
current_compose=(docker compose -f "$iam_root/releases/$current_tag/compose.production.yaml"
  -f "$iam_root/releases/$current_tag/compose.production.host-nginx.yaml" --env-file "$env_file")
current_rev=$(IAM_RELEASE_TAG=$current_tag "${current_compose[@]}" exec -T postgres \
  psql -U iam -d iam -Atc 'SELECT version_num FROM alembic_version')

if [[ -z $new_head || -z $current_rev || $new_head != "$current_rev" ]]; then
  echo "Schema gate: current=$current_rev target=$new_head. Backup, restore drill and explicit migration authorization are required." >&2
  exit 2
fi

rollback() {
  echo "Restoring previous IAM containers ($current_tag)." >&2
  IAM_RELEASE_TAG=$current_tag "${current_compose[@]}" up -d --no-deps --no-build api console
}

if ! "${new_compose[@]}" up -d --no-deps --no-build api console; then
  rollback
  exit 1
fi

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
  echo 'New IAM release did not become ready.' >&2
  rollback
  exit 1
fi

printf '%s\n' "$release_tag" > "$current_tag_file.new"
chmod 0600 "$current_tag_file.new"
mv -f "$current_tag_file.new" "$current_tag_file"
rm -f "$incoming_dir/images.tar.gz" "$incoming_dir/source.tar.gz"
echo "IAM release $release_tag is ready. No migration was run."
