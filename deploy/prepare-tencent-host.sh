#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $EUID -ne 0 || $# -ne 2 ]]; then
  echo 'Usage: sudo prepare-tencent-host.sh <admin-email> <ci-public-key-file>' >&2
  exit 1
fi

admin_email=$1
ci_public_key_file=$2
if [[ ! $admin_email =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+$ || ! -f $ci_public_key_file ]]; then
  echo 'A valid admin email and existing CI public key file are required.' >&2
  exit 1
fi

read -r ci_public_key < "$ci_public_key_file"
if [[ ! $ci_public_key =~ ^ssh-ed25519[[:space:]]+[A-Za-z0-9+/=]+([[:space:]].*)?$ ]]; then
  echo 'The CI public key must be an SSH Ed25519 public key.' >&2
  exit 1
fi

iam_root=/opt/iam
shared_dir=$iam_root/shared
env_file=$shared_dir/.env.production.local
if [[ -e $env_file || -e $shared_dir/initialized ]]; then
  echo 'IAM host is already prepared; refusing to replace existing secrets.' >&2
  exit 1
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
for source_file in receive-release.sh iam-ip.nginx.conf; do
  if [[ ! -f $script_dir/$source_file ]]; then
    echo "Missing setup companion: $source_file" >&2
    exit 1
  fi
done

umask 077
install -d -o root -g root -m 0755 "$iam_root" "$iam_root/bin" "$iam_root/releases"
install -d -o root -g root -m 0700 "$shared_dir" "$shared_dir/tls" "$shared_dir/nginx"
install -d -o root -g 10001 -m 0750 "$shared_dir/secrets"

if ! id iamdeploy >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /home/iamdeploy --shell /bin/bash iamdeploy
fi
install -d -o iamdeploy -g iamdeploy -m 0700 /home/iamdeploy/.ssh /home/iamdeploy/incoming
authorized_keys=/home/iamdeploy/.ssh/authorized_keys
touch "$authorized_keys"
if ! grep -Fqx "restrict $ci_public_key" "$authorized_keys"; then
  printf 'restrict %s\n' "$ci_public_key" >> "$authorized_keys"
fi
chown iamdeploy:iamdeploy "$authorized_keys"
chmod 0600 "$authorized_keys"

install -o root -g root -m 0755 "$script_dir/receive-release.sh" "$iam_root/bin/receive-release.sh"
install -o root -g root -m 0644 "$script_dir/iam-ip.nginx.conf" "$shared_dir/nginx/iam-ip.nginx.conf"
printf '%s\n' 'iamdeploy ALL=(root) NOPASSWD: /opt/iam/bin/receive-release.sh *' > /etc/sudoers.d/iamdeploy
chmod 0440 /etc/sudoers.d/iamdeploy
visudo -cf /etc/sudoers.d/iamdeploy >/dev/null

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 \
  -out "$shared_dir/secrets/oidc-signing-key.pem" >/dev/null 2>&1
chown root:10001 "$shared_dir/secrets/oidc-signing-key.pem"
chmod 0640 "$shared_dir/secrets/oidc-signing-key.pem"

openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
  -keyout "$shared_dir/tls/ip.key" -out "$shared_dir/tls/ip.crt" \
  -subj '/CN=175.178.62.55' -addext 'subjectAltName=IP:175.178.62.55' \
  >/dev/null 2>&1
chmod 0600 "$shared_dir/tls/ip.key"
chmod 0644 "$shared_dir/tls/ip.crt"

postgres_password=$(openssl rand -hex 32)
jwt_secret=$(openssl rand -hex 32)
bootstrap_password=$(openssl rand -hex 24)
{
  printf 'IAM_DOMAIN=175.178.62.55\n'
  printf 'IAM_RELEASE_TAG=bootstrap\n'
  printf 'IAM_POSTGRES_PASSWORD=%s\n' "$postgres_password"
  printf 'IAM_JWT_SECRET=%s\n' "$jwt_secret"
  printf 'IAM_ADMIN_EMAIL=%s\n' "$admin_email"
  printf 'IAM_BOOTSTRAP_ADMIN_PASSWORD=%s\n' "$bootstrap_password"
  printf 'IAM_OIDC_SIGNING_KEY_FILE=%s\n' "$shared_dir/secrets/oidc-signing-key.pem"
  printf 'IAM_MODEL_USAGE_API_KEY=\n'
  printf 'IAM_MODEL_QUOTA_ENFORCEMENT_ENABLED=false\n'
  printf 'IAM_ALLOW_PUBLIC_REGISTRATION=false\n'
} > "$env_file"
chmod 0600 "$env_file"

echo 'IAM host prepared. No container, Nginx route or database migration was started.'
echo 'TLS certificate is self-signed; clients must trust it until an IAM domain is available.'
