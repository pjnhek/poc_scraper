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
# The v2/v1 OCI instance-metadata endpoints below do not carry a "publicIp"
# field on this account/region (confirmed live during 13-04 Task 2: both the
# v2 instance document and the v1/v2 vnics documents list only privateIp).
# The public IP is an ephemeral NAT'd address associated with the VNIC, not
# metadata the instance itself is handed, so an external echo service is the
# reliable fallback (the instance's own outbound traffic already egresses
# via that public IP).
PUBLIC_IP=$(curl -fsS -H "Authorization: Bearer Oracle" http://169.254.169.254/opc/v2/instance/ 2>/dev/null \
  | grep -o '"publicIp" *: *"[^"]*"' | cut -d'"' -f4 || true)
if [ -z "$PUBLIC_IP" ]; then
  PUBLIC_IP=$(curl -fsS http://169.254.169.254/opc/v1/vnics/0/publicIp 2>/dev/null || true)
fi
if [ -z "$PUBLIC_IP" ]; then
  PUBLIC_IP=$(curl -fsS https://ifconfig.me 2>/dev/null || true)
fi
if [ -z "$PUBLIC_IP" ]; then
  PUBLIC_IP=$(curl -fsS https://ipv4.icanhazip.com 2>/dev/null | tr -d '[:space:]' || true)
fi
if [ -z "$PUBLIC_IP" ]; then
  echo "Could not resolve the public IP from OCI instance metadata or an" >&2
  echo "external echo service; set MCP_PUBLIC_HOSTNAME manually in $ENV_FILE and re-run." >&2
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
# Enforce owner-only perms every run: the file holds EXA_API_KEY and cat> would
# otherwise leave it world-readable (default umask 022 -> 0644) to the ubuntu
# account. Applies to a just-written or a pre-existing file.
chmod 600 "$ENV_FILE"

CADDY_HOSTNAME=$(grep '^MCP_PUBLIC_HOSTNAME=' "$ENV_FILE" | cut -d= -f2-)

# --- landing page: a human-readable page served at / so a browser visit to the
# root explains how to connect (the machine endpoint stays at /mcp, proxied
# below). Heredoc is unquoted so ${CADDY_HOSTNAME} fills in the live hostname;
# bash does no brace expansion in heredoc bodies, so the CSS braces are safe.
mkdir -p /opt/poc-scraper/site
cat >/opt/poc-scraper/site/index.html <<EOF
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>poc_scraper - Grounded Account-Research MCP Server</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1a1a1a; background: #fafafa; }
  main { max-width: 760px; margin: 0 auto; padding: 3rem 1.25rem 4rem; }
  h1 { font-size: 1.7rem; margin: 0 0 .2rem; letter-spacing: -.02em; }
  .tag { color: #666; margin: 0 0 2rem; }
  h2 { font-size: 1.05rem; margin: 2.2rem 0 .5rem; }
  p { margin: .6rem 0; }
  ul { margin: .6rem 0; padding-left: 1.25rem; }
  li { margin: .35rem 0; }
  code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .86rem; }
  pre { background: #f0f0f0; border: 1px solid #e2e2e2; border-radius: 8px; padding: .8rem 1rem; overflow-x: auto; }
  .url { display: inline-block; background: #eef; border: 1px solid #dde; border-radius: 6px; padding: .15rem .45rem; }
  .note { color: #666; font-size: .9rem; border-left: 3px solid #ddd; padding-left: 1rem; }
  a { color: #2b6cb0; }
  footer { margin-top: 3rem; color: #888; font-size: .85rem; }
  @media (prefers-color-scheme: dark) {
    body { color: #e6e6e6; background: #16181c; }
    .tag, .note, footer { color: #9aa0a6; }
    pre { background: #1e2127; border-color: #2c303a; }
    .url { background: #202634; border-color: #313a52; }
    a { color: #7aa7e0; }
    .note { border-left-color: #333; }
  }
</style>
</head>
<body>
<main>
  <h1>poc_scraper</h1>
  <p class="tag">A grounded account-research pipeline, exposed as an MCP server.</p>

  <p>This is the <strong>live demo tier</strong>: given a company domain it retrieves recent, cited evidence (about pages and last-90-day news), numbered so a calling agent can trace every claim back to its source, then the agent scores each ICP axis from that evidence and calls <code>score_account</code>, which computes the weighted total and verdict deterministically. Cited evidence retrieval is rationed to 5 calls per IP per hour and 25 per day; <code>score_account</code> is unrationed pure arithmetic on top of it. The full pipeline (personas, citation-checked outreach) is BYOK and runs locally.</p>

  <h2>MCP endpoint</h2>
  <p><span class="url">https://${CADDY_HOSTNAME}/mcp</span></p>

  <h2>Connect from Codex</h2>
  <pre>codex mcp add poc-scraper --url https://${CADDY_HOSTNAME}/mcp</pre>

  <h2>Connect from Claude Code</h2>
  <pre>claude mcp add --transport http poc-scraper https://${CADDY_HOSTNAME}/mcp</pre>

  <h2>Connect from Claude Desktop</h2>
  <p>Add to <code>claude_desktop_config.json</code>:</p>
  <pre>{
  "mcpServers": {
    "poc-scraper": {
      "command": "npx",
      "args": ["mcp-remote", "https://${CADDY_HOSTNAME}/mcp"]
    }
  }
}</pre>

  <h2>Any other MCP client</h2>
  <pre>npx mcp-remote https://${CADDY_HOSTNAME}/mcp</pre>

  <h2>First call</h2>
  <p>Once connected, run the <code>research_account</code> prompt on a domain. In Claude Code that is a slash command:</p>
  <pre>/mcp__poc-scraper__research_account notion.so</pre>
  <p>It returns a six-step flow for the agent to follow: retrieve cited evidence, read the rubric, score each ICP axis carrying an [N] citation, call <code>score_account</code>, present the verdict, then propose personas and outreach hooks. To drive the pieces yourself instead:</p>
  <ul>
    <li><code>get_account_evidence(domain)</code> returns numbered, cited evidence. Optional <code>news_days</code> widens or narrows the news window (clamped 7-365, default 90).</li>
    <li><code>score_account(...)</code> takes your four 1-5 axis scores and returns the weighted total and verdict. Unrationed: pure arithmetic, no LLM call.</li>
    <li><code>icp://rubric</code> and <code>icp://eval-report</code> are readable resources: the live rubric this server scores against, and the eval calibration narrative behind its groundedness numbers.</li>
  </ul>

  <h2>What comes back</h2>
  <p>Evidence arrives numbered, and those indices are the citation vocabulary for everything downstream. Real output for <code>notion.so</code>, trimmed:</p>
  <pre>{
  "retrieval_status": "ok",
  "justifications": [
    {"index": 1, "summary": "Llms",
     "citation": {"url": "https://www.notion.so/llms.txt", "source": "exa"}},
    {"index": 6, "summary": "Notion just turned its workspace into a hub for AI agents",
     "citation": {"url": "https://techcrunch.com/2026/05/13/...", "source": "exa"}}
  ]
}</pre>
  <p>Score those axes, cite an index in each reason, and <code>score_account</code> returns:</p>
  <pre>{
  "domain": "notion.so",
  "total": 4.2,
  "verdict": "strong",
  "verdict_description": "Clear ICP fit; prioritize outreach.",
  "weights": {"support_volume": 0.4, "ai_maturity": 0.3,
              "stage_fit": 0.2, "channel_breadth": 0.1},
  "verdict_thresholds": {"strong": 4, "borderline": 2.5, "weak": 0}
}</pre>
  <p class="note">The weights and thresholds ship with every score, so the total is checkable by hand: 4(0.4) + 5(0.3) + 4(0.2) + 3(0.1) = 4.2, clearing the 4.0 strong threshold. An agent made the judgment; it did not do the arithmetic. Invalid input and provider errors come back as sanitized one-line messages, never stack traces.</p>

  <footer>
    Source, the full BYOK tier, and how it works:
    <a href="https://github.com/pjnhek/poc_scraper">github.com/pjnhek/poc_scraper</a>
  </footer>
</main>
</body>
</html>
EOF

# --- Caddyfile: HTTPS reverse proxy for the MCP endpoint at /mcp, plus the
# static landing page at / for human visitors.
cat >/etc/caddy/Caddyfile <<EOF
$CADDY_HOSTNAME {
    handle /mcp* {
        reverse_proxy 127.0.0.1:8000 {
            # Overwrite any client-supplied Fly-Client-IP with the real TCP peer.
            # The app trusts this header verbatim as the rate-limit bucket key
            # (src/mcp_server/limits.py); without this line a caller could send its
            # own Fly-Client-IP and pick a fresh per-IP bucket on every request.
            header_up Fly-Client-IP {remote_host}
        }
    }
    handle {
        root * /opt/poc-scraper/site
        file_server
    }
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
