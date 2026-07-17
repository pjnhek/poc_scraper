#!/usr/bin/env bash
# Idempotent setup/redeploy script for the poc-scraper-mcp Oracle Always Free VM.
#
# Runs as root. Two supported invocations:
#   1. As the OCI instance's user-data at first boot (cloud-init executes a
#      plain "#!/bin/bash" user-data script directly; no separate cloud-init
#      YAML file is needed). This is what deploy/oracle/provision.sh passes
#      via --user-data-file.
#   2. Manually over SSH, to redeploy after `git pull` or to pick up a newly
#      set EXA_API_KEY:
#        ssh -o StrictHostKeyChecking=accept-new ubuntu@<host> 'sudo bash -s' \
#          < deploy/oracle/setup.sh
#
# Installs Docker + Caddy, builds this repo's committed Dockerfile, runs the
# container bound to loopback only, and fronts it with Caddy for automatic
# HTTPS at <public-ip>.sslip.io (sslip.io resolves any dotted-IP subdomain to
# that IP, so no DNS account is needed).
#
# Every step is re-runnable: package installs are skipped if already present,
# the env file (which holds EXA_API_KEY) is written once and never
# overwritten, and the container/Caddy config are simply replaced each run.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/pjnhek/poc_scraper.git}"
REPO_DIR="/opt/poc-scraper/repo"
ENV_FILE="/opt/poc-scraper/mcp.env"
CONTAINER_NAME="poc-scraper-mcp"

if [ "$(id -u)" -ne 0 ]; then
  echo "setup.sh must run as root (sudo bash -s < deploy/oracle/setup.sh)" >&2
  exit 1
fi

apt-get update -y
apt-get install -y ca-certificates curl gnupg git

# --- swap safety net -------------------------------------------------------
# The Always Free fallback shape (VM.Standard.E2.1.Micro) has 1GB RAM, not
# enough headroom for `docker build`'s `uv sync` step without it. Cheap
# insurance on any shape below 2GB.
TOTAL_MEM_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
if [ "$TOTAL_MEM_KB" -lt 2097152 ] && [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi

# --- Docker ------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  ARCH=$(dpkg --print-architecture)
  CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")
  echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $CODENAME stable" \
    >/etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io
fi

# --- Caddy ---------------------------------------------------------------
if ! command -v caddy >/dev/null 2>&1; then
  apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    >/etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy
fi

# --- host firewall ---------------------------------------------------------
# OCI's Ubuntu images ship a default-deny iptables ruleset out of the box.
# The cloud-level Security List/NSG (opened separately, see docs/DEPLOY.md;
# the OCI console or CLI, not this script) is necessary but NOT sufficient:
# the host firewall must also allow 80 (ACME HTTP-01 challenge) and 443.
for PORT in 80 443; do
  iptables -C INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null \
    || iptables -I INPUT 1 -p tcp --dport "$PORT" -j ACCEPT
done
if ! command -v netfilter-persistent >/dev/null 2>&1; then
  apt-get install -y iptables-persistent || true
fi
netfilter-persistent save 2>/dev/null || true

# --- app source --------------------------------------------------------
mkdir -p /opt/poc-scraper
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" pull --ff-only
else
  git clone --depth 1 "$REPO_URL" "$REPO_DIR"
fi

# --- public hostname (sslip.io, no DNS account needed) ---------------------
PUBLIC_IP=$(curl -fsS -H "Authorization: Bearer Oracle" http://169.254.169.254/opc/v2/instance/ 2>/dev/null \
  | grep -o '"publicIp" *: *"[^"]*"' | cut -d'"' -f4 || true)
if [ -z "$PUBLIC_IP" ]; then
  PUBLIC_IP=$(curl -fsS http://169.254.169.254/opc/v1/vnics/0/publicIp 2>/dev/null || true)
fi
if [ -z "$PUBLIC_IP" ]; then
  echo "Could not resolve the public IP from OCI instance metadata; set" >&2
  echo "MCP_PUBLIC_HOSTNAME manually in $ENV_FILE and re-run." >&2
  PUBLIC_IP="UNKNOWN"
fi
HOSTNAME_VALUE="${PUBLIC_IP}.sslip.io"

# --- env file (written once; EXA_API_KEY must survive every re-run) --------
if [ ! -f "$ENV_FILE" ]; then
  cat >"$ENV_FILE" <<EOF
MCP_DEMO_MODE=1
MCP_HTTP_HOST=0.0.0.0
MCP_PUBLIC_HOSTNAME=$HOSTNAME_VALUE
EXA_API_KEY=REPLACE_ME
EOF
  echo "Wrote $ENV_FILE with a placeholder EXA_API_KEY."
  echo "Edit it (EXA_API_KEY=<your key>), then re-run this script to pick it up."
fi

# --- Caddyfile: automatic HTTPS reverse proxy to the loopback-only container
CADDY_HOSTNAME=$(grep '^MCP_PUBLIC_HOSTNAME=' "$ENV_FILE" | cut -d= -f2-)
cat >/etc/caddy/Caddyfile <<EOF
$CADDY_HOSTNAME {
    reverse_proxy 127.0.0.1:8000
}
EOF
systemctl enable --now caddy
systemctl reload caddy 2>/dev/null || systemctl restart caddy

# --- build and (re)start the container -------------------------------------
docker build -t poc-scraper-mcp:latest "$REPO_DIR"
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
docker run -d --name "$CONTAINER_NAME" --restart unless-stopped \
  --env-file "$ENV_FILE" -p 127.0.0.1:8000:8000 poc-scraper-mcp:latest

if grep -q 'REPLACE_ME' "$ENV_FILE"; then
  echo "WARNING: EXA_API_KEY is still a placeholder in $ENV_FILE." >&2
  echo "The container will crash-loop until you set it and re-run this script." >&2
fi

echo "Public endpoint (once the cloud-level Security List/NSG allows 443): https://$CADDY_HOSTNAME/mcp"
