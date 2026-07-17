# Deploying the hosted MCP demo

This runbook covers deploying `poc_scraper`'s MCP server as the public,
demo-mode-only hosted endpoint (HOST-03, HOST-06). The primary target is
Oracle Cloud Infrastructure's Always Free tier (a raw compute VM, $0/month).
Hugging Face Spaces and Fly.io are kept as documented alternatives below,
each blocked on a payment requirement that Oracle's Always Free tier avoids.

## Deploy-target decision chain (13-04)

The original plan targeted Fly.io. Both of the first two candidates hit a
payment gate that the operator declined:

1. **Fly.io (original plan target).** `fly apps create` failed with "We need
   your payment information": Fly.io now requires a card on file even for its
   otherwise-free allowances.
2. **Hugging Face Spaces (first pivot).** `hf repo create ... --type space
   --sdk docker` returned HTTP 402: Docker/Gradio Spaces now require a PRO
   subscription ($9/month); only static (non-Docker) Spaces are free.
3. **Oracle Cloud Always Free (current target).** A raw compute VM under
   OCI's Always Free tier. A card is required at account signup for identity
   verification only; Free Tier accounts cannot be charged unless the
   operator explicitly upgrades to Pay As You Go. This is the most
   setup-heavy of the three (raw VM, Docker, host firewall, DNS-free
   hostname, TLS all assembled by hand instead of a managed platform), which
   is the tradeoff for zero ongoing cost and no card risk.

The `Dockerfile` (shared across all three targets), `fly.toml`, and the HF
Space artifacts stay committed; nothing about the pivot required deleting
prior work; see the appendices below.

## MCP_PUBLIC_HOSTNAME (applies to every target)

`MCP_PUBLIC_HOSTNAME` is a `Settings` field (`src/config.py`) distinct from
`MCP_HTTP_HOST`. `MCP_HTTP_HOST` is a pure bind address (for example
`0.0.0.0` in the container); `MCP_PUBLIC_HOSTNAME` is the externally-visible
hostname a real client's `Host` header carries (for example
`203.0.113.10.sslip.io`, `<owner>-poc-scraper-mcp.hf.space`, or
`poc-scraper-mcp.fly.dev`).

- The server refuses to start when serving HTTP on a non-loopback bind (such
  as `0.0.0.0`) with no `MCP_PUBLIC_HOSTNAME` configured. This fail-fast guard
  (`guard_non_loopback_requires_public_hostname` in
  `src/mcp_server/__main__.py`) matches the project's existing fail-loud
  precedent: a misconfigured container dies visibly at startup instead of
  serving with a wrong or empty allowlist.
- When set, `MCP_PUBLIC_HOSTNAME` sources an additional entry in
  `build_server`'s `TransportSecuritySettings` allowlist so a real client's
  `Host` header is accepted without allowlisting the bind address itself.
- Local development is unaffected: `make mcp-http` and `make mcp-demo` default
  to a loopback bind (`127.0.0.1`), which the guard and the existing localhost
  allowlist handle unchanged.
- This variable could not be added to `.env.example` in plan 13-01 (file
  outside that session's file-access permissions), so it is documented here
  instead.
- On Oracle, the hostname comes from [sslip.io](https://sslip.io): any
  dotted-IP subdomain (`<public-ip>.sslip.io`) resolves to that IP with no DNS
  account or domain purchase needed. Caddy performs the ACME HTTP-01
  challenge against that same hostname to issue a real TLS certificate.

## Oracle Cloud Always Free (primary)

**Status:** live. Provisioned and deployed against a real OCI Always Free
account on 2026-07-17 (13-04 Task 2); the commands below are the confirmed
sequence, corrected against what actually happened. See "Live provisioning
findings" below for the deviations found during that run.

### Decision mapping (D-01 through D-04, D-13)

- **D-01 (idle-behavior cost intent):** a raw Always Free VM has no
  suspend-on-idle primitive (unlike Fly's `auto_stop_machines`). D-01's
  actual goal, keeping cost near zero, is satisfied a different way: the VM
  runs 24/7 at **$0/month** under the Always Free tier rather than by
  idling. `DemoLimiter` counters therefore persist across quiet periods (no
  suspend-triggered reset) and reset only on an explicit redeploy or crash,
  same tradeoff class as the other two targets accept.
- **D-02 (cost ceiling, up to ~$5/mo acceptable):** Always Free is $0/month
  by construction as long as the instance stays within Always Free shape and
  storage limits (see "Cost" below).
- **D-03 (single-instance pin):** there is exactly one VM; no cluster or
  autoscaling group exists to accidentally scale out, so `DemoLimiter`'s
  in-memory counters stay globally correct by construction, the same
  single-machine intent as Fly's `fly scale count 1` pin.
- **D-04 (app identity):** the instance display name and Caddy site block
  both use `poc-scraper-mcp`, vendor-neutral and consistent with the Fly app
  name and HF Space name.
- **D-13 (deploy stays a deliberate manual act):** `deploy/oracle/setup.sh`
  and `deploy/oracle/provision.sh` are committed (no secrets; `EXA_API_KEY`
  is injected by the operator directly on the VM, see below). There is no
  GitHub Actions CD; `make provision-oracle` and `make deploy-oracle` are
  explicit operator commands.

### Prerequisites

1. Create an Oracle Cloud (OCI) account: https://signup.oraclecloud.com. A
   card is required at signup for identity verification only; Free Tier
   accounts cannot be charged unless explicitly upgraded to Pay As You Go.
   Note your **home region** once signup completes; every command below runs
   against that region.
2. Install the `oci` CLI:
   ```
   brew install oci-cli
   ```
3. Authenticate. Either works; the browser flow is faster for a first setup:
   ```
   oci session authenticate
   ```
   or configure a long-lived API key profile per Oracle's docs if you prefer
   not to re-authenticate each session.
4. One-time network setup. The OCI console's Networking > Virtual Cloud
   Networks > **Start VCN Wizard** > "Create VCN with Internet Connectivity"
   does this in one click and is the fastest path for a first VM. It can also
   be done entirely from the CLI (confirmed live, 13-04 Task 2), useful when
   the operator cannot use the console in this environment:
   ```
   VCN_ID=$(oci network vcn create --compartment-id "$OCI_COMPARTMENT_ID" \
     --cidr-block "10.0.0.0/16" --display-name "poc-scraper-vcn" \
     --dns-label "pocscraper" --wait-for-state AVAILABLE \
     --query 'data.id' --raw-output)

   IGW_ID=$(oci network internet-gateway create \
     --compartment-id "$OCI_COMPARTMENT_ID" --vcn-id "$VCN_ID" \
     --is-enabled true --display-name "poc-scraper-igw" \
     --wait-for-state AVAILABLE --query 'data.id' --raw-output)

   RT_ID=$(oci network vcn get --vcn-id "$VCN_ID" \
     --query 'data."default-route-table-id"' --raw-output)
   oci network route-table update --rt-id "$RT_ID" --force \
     --route-rules "[{\"destination\": \"0.0.0.0/0\", \"destinationType\": \"CIDR_BLOCK\", \"networkEntityId\": \"$IGW_ID\"}]"

   SL_ID=$(oci network vcn get --vcn-id "$VCN_ID" \
     --query 'data."default-security-list-id"' --raw-output)
   oci network security-list update --security-list-id "$SL_ID" --force \
     --ingress-security-rules '[
       {"protocol":"6","source":"0.0.0.0/0","sourceType":"CIDR_BLOCK","isStateless":false,"tcpOptions":{"destinationPortRange":{"min":22,"max":22}}},
       {"protocol":"6","source":"0.0.0.0/0","sourceType":"CIDR_BLOCK","isStateless":false,"tcpOptions":{"destinationPortRange":{"min":80,"max":80}}},
       {"protocol":"6","source":"0.0.0.0/0","sourceType":"CIDR_BLOCK","isStateless":false,"tcpOptions":{"destinationPortRange":{"min":443,"max":443}}}
     ]' \
     --egress-security-rules '[{"protocol":"all","destination":"0.0.0.0/0","destinationType":"CIDR_BLOCK","isStateless":false}]'

   export OCI_SUBNET_ID=$(oci network subnet create \
     --compartment-id "$OCI_COMPARTMENT_ID" --vcn-id "$VCN_ID" \
     --cidr-block "10.0.0.0/24" --display-name "poc-scraper-public-subnet" \
     --dns-label "public" --route-table-id "$RT_ID" \
     --security-list-ids "[\"$SL_ID\"]" --prohibit-public-ip-on-vnic false \
     --wait-for-state AVAILABLE --query 'data.id' --raw-output)
   ```
   Either path opens 22 (SSH), 80 (ACME HTTP-01), and 443 (HTTPS) on the
   default security list and routes 0.0.0.0/0 through the internet gateway.
   Note the resulting subnet OCID either way.
5. Generate a dedicated SSH key pair for this deploy (do not reuse a
   general-purpose key; never commit it):
   ```
   ssh-keygen -t ed25519 -f ~/.ssh/poc_scraper_oracle -N ""
   ```

### Provision the instance

```
export OCI_COMPARTMENT_ID=<your compartment OCID>
export OCI_AD=$(oci iam availability-domain list \
  --compartment-id "$OCI_COMPARTMENT_ID" \
  --query 'data[0].name' --raw-output)
export OCI_SUBNET_ID=<the public subnet OCID from step 4 above>
export SSH_PUBLIC_KEY_FILE=~/.ssh/poc_scraper_oracle.pub
make provision-oracle
```

Before provisioning, make sure the commit you want deployed is pushed to
`origin/main` (or set `REPO_URL`/branch to wherever it lives).
`deploy/oracle/setup.sh` clones from GitHub, not from your local working
tree; a local-only commit is invisible to the VM and produces a confusing
"Dockerfile not found" build failure (see "Live provisioning findings"
below).

`deploy/oracle/provision.sh` tries the Always Free ARM shape first
(`VM.Standard.A1.Flex`, 1 OCPU / 6GB), and falls back to the smaller Always
Free AMD shape (`VM.Standard.E2.1.Micro`) if A1.Flex reports a
capacity/limit error in that availability domain. This is a known Always
Free gotcha: A1.Flex capacity is finite per availability domain and
frequently exhausted; E2.1.Micro is always obtainable but has only 1GB RAM
(the setup script adds a 2GB swapfile to compensate during the Docker
build). The instance boots Ubuntu 22.04, looked up dynamically per shape so
the ARM/AMD image OCID split never needs to be hand-maintained.

The instance's OCI user-data is `deploy/oracle/setup.sh` itself: cloud-init
runs a plain `#!/bin/bash` user-data script directly at first boot, so the
same script that provisions the VM is also what an operator re-runs by hand
later. No separate cloud-init YAML file exists; keeping one script avoids
config drift between "first boot" and "redeploy" behavior.

### Open the cloud-level firewall (the classic OCI gotcha)

OCI has **two** independent firewalls; both must allow inbound 443 (and 80,
for the ACME challenge) or the deploy is unreachable even though the VM's
own iptables (opened by `setup.sh`) is correct:

1. **Security List / Network Security Group** (cloud-level, OCI console or
   CLI): Networking > Virtual Cloud Networks > `<vcn>` > Security Lists >
   Default Security List > Add Ingress Rules. Add two stateless-off ingress
   rules: source `0.0.0.0/0`, TCP, destination port `443`; and the same for
   port `80`.
2. **Host firewall (iptables)**: already opened by `deploy/oracle/setup.sh`
   for ports 80 and 443, persisted via `netfilter-persistent`.

Both are necessary. Missing either one produces a hang or connection-refused
on the public URL with a clean `docker ps`/`caddy` status on the VM itself,
the single most common Oracle deploy pitfall.

### Inject EXA_API_KEY (the executor cannot read this value)

`setup.sh` writes `/opt/poc-scraper/mcp.env` on the VM with a placeholder,
then leaves it alone on every later run so the real value is never
overwritten. The operator sets it directly on the VM, never in this repo:

```
ssh -o StrictHostKeyChecking=accept-new ubuntu@<public-ip>.sslip.io
sudo nano /opt/poc-scraper/mcp.env   # replace EXA_API_KEY=REPLACE_ME
exit
```

Then pick the new value up (also how you redeploy after `git pull`):

```
make deploy-oracle ORACLE_HOST=<public-ip>.sslip.io
```

If the dedicated deploy key is not loaded in your ssh-agent, pass it
explicitly (otherwise ssh only offers your default keys and fails with
`Permission denied (publickey)`):

```
make deploy-oracle ORACLE_HOST=<public-ip>.sslip.io SSH_KEY=~/.ssh/poc_scraper_oracle
```

### app_port and the container

`setup.sh` builds this repo's `Dockerfile` on the VM and runs it bound to
`127.0.0.1:8000` only (not the public interface directly); Caddy is the only
process listening on the public interface (80/443), terminating TLS and
reverse-proxying to the loopback-bound container. This is a defense-in-depth
step beyond what HF/Fly need, since on a raw VM there is no managed edge
doing that isolation for you.

### Single-instance and idle behavior (mapping D-01/D-03)

See "Decision mapping" above. In short: one VM, always on, $0/month; no
suspend/resume state machine to reason about.

### Verifying the deploy

Replace `<host>` with the confirmed `<public-ip>.sslip.io` hostname.

1. Confirm the MCP endpoint responds to a JSON-RPC initialize call:
   ```
   curl -sS -X POST https://<host>/mcp \
     -H "Accept: application/json, text/event-stream" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"deploy-check","version":"0.1"}}}'
   ```
   Expect a non-421, non-5xx response. A 421 means the `Host` header did not
   match the `TransportSecuritySettings` allowlist; confirm
   `MCP_PUBLIC_HOSTNAME` in `/opt/poc-scraper/mcp.env` matches the real
   hostname exactly.
2. Check container logs for the startup lines: the resolved tier line must
   say `thin`, and the demo-limits line must show the 5/25/5 defaults:
   ```
   ssh ubuntu@<host> 'docker logs poc-scraper-mcp | tail -20'
   ```
3. Confirm HTTP redirects to HTTPS:
   ```
   curl -sI http://<host>/mcp
   ```
   Caddy issues a real Let's Encrypt certificate on first request to `<host>`
   via the ACME HTTP-01 challenge (port 80 must already be open, see above).
4. Confirm a forged `Host` header is rejected. Two layers reject it, tested
   independently live (13-04 Task 2): Caddy's own vhost matching rejects a
   mismatched `Host`/`:authority` before the request ever reaches the
   container (an empty `200` with `content-length: 0`, no corresponding line
   in `docker logs`), and the app's own `TransportSecuritySettings` allowlist
   independently rejects it with `421 Invalid Host header` when hit directly
   (bypass Caddy over SSH to confirm this layer specifically):
   ```
   ssh ubuntu@<host> 'curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8000/mcp -H "Host: evil.example.com" -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-06-18\",\"capabilities\":{},\"clientInfo\":{\"name\":\"x\",\"version\":\"0\"}}}"'
   ```
   Expect `421`.

### Live provisioning findings (13-04 Task 2)

Recorded from the first live run against a real OCI Always Free account
(2026-07-17, `us-sanjose-1`), following the same discipline as the Fly
appendix's "Dry run findings" above.

1. **Network setup ran non-interactively via the CLI**, not the console
   wizard (no console access in this environment). The exact commands are
   folded into "Prerequisites" step 4 above; they produced a VCN, one public
   subnet, an internet gateway, a default route to it, and a security list
   with 22/80/443 open, matching what the console wizard would have created.
2. **`VM.Standard.A1.Flex` was out of capacity** in `US-SANJOSE-1-AD-1` (this
   region has exactly one availability domain): `oci compute instance
   launch` returned `InternalError: Out of host capacity.` This is the
   documented Always Free gotcha, not a bug; `provision.sh` caught it and
   fell back to `VM.Standard.E2.1.Micro` automatically, as designed. No
   script change was needed here.
3. **The instance's public IP is not present in OCI's instance-metadata
   service on this account.** `setup.sh` originally read
   `curl -H "Authorization: Bearer Oracle" http://169.254.169.254/opc/v2/instance/`
   and the `/opc/v1/vnics/0/publicIp` fallback, expecting a `publicIp` field;
   live testing found neither the v2 instance document nor the v1/v2 vnics
   documents carry that field on this account/region (both list only
   `privateIp`). The public IP is an ephemeral address NAT'd onto the VNIC by
   OCI's edge, not metadata handed to the instance. **Fixed** (Rule 1 bug):
   `setup.sh` now falls back to an external echo service
   (`https://ifconfig.me`, then `https://ipv4.icanhazip.com`) after both
   metadata attempts return empty, since the instance's own outbound traffic
   already egresses via that same public IP. Confirmed working: resolved
   `170.9.7.144.sslip.io` correctly on the corrected script.
4. **`git clone` on the VM pulled a tree with no `Dockerfile`** on the first
   run: this repository's `origin/main` on GitHub was 12 commits behind the
   local branch that authored the Oracle scaffolding (the phase 13 commits,
   including the one that added `Dockerfile`, had never been pushed).
   `setup.sh` clones from `origin`, not from the local working tree, so the
   VM silently got a pre-Dockerfile snapshot and `docker build` failed with
   `open Dockerfile: no such file or directory`. **Fixed** by pushing
   `main` to `origin` (a plain fast-forward; nothing to reconcile) before
   re-running `setup.sh`. This is a process gotcha, not a script bug; the
   "before provisioning" note under "Provision the instance" above now
   calls it out explicitly.
5. **Live transport verification (RESEARCH assumption A1): CONFIRMED.** A
   JSON-RPC `initialize` POST to `https://170.9.7.144.sslip.io/mcp` with the
   real hostname as `Host` returned `200` with a valid MCP handshake response
   (not `421`, not `5xx`); `http://170.9.7.144.sslip.io/mcp` returned a `308`
   redirect to `https://`. `docker logs` showed the expected startup lines:
   tier resolved `thin (exa-only)` and demo limits `5 calls/ip/hour, 25/day
   global, exa results clamp 5`. No allowlist or `TransportSecuritySettings`
   code change was needed; A1 held as designed on the first live attempt.
6. **Exactly one instance and one container** were confirmed via
   `oci compute instance list --display-name poc-scraper-mcp` (one result)
   and `docker ps -a` on the VM (one `poc-scraper-mcp` container, `Up`,
   `restart unless-stopped`), satisfying D-03/HOST-06's single-machine
   intent for the `DemoLimiter` counters.

### Live real-client verification (13-04 Task 3, D-14)

Performed live against `https://170.9.7.144.sslip.io/mcp` with the official
MCP Python SDK's streamable-http client, operator watching the raw payloads
as they came back (this is the D-14 checkpoint; it is deliberately not
scripted):

1. `initialize` succeeded: server `poc-scraper` v1.28.1, tools list
   `["get_account_evidence"]`.
2. **HOST-03 confirmed live:** `get_account_evidence("notion.so")` returned
   `retrieval_status: "ok"` with real `about_text` and 7+ numbered
   justifications, each carrying a citation URL (for example
   `https://www.notion.so/llms.txt`, a news article dated 2026-05-13), source
   `exa`. This is also when the operator set the real `EXA_API_KEY` on the VM
   for the first time (see "Inject EXA_API_KEY" above); it had been left at
   the `setup.sh` placeholder since the Task 2 provisioning run.
3. **HOST-05 confirmed live:** `get_account_evidence("not-a-domain")`
   returned `isError: true` with exactly one plain line,
   `Error executing tool get_account_evidence: invalid domain`. No stack
   trace, environment variable name, key fragment, or file path leaked.

Both checks pass. HOST-03 and the live half of HOST-05 are now confirmed
end to end against the real deployment, not only by the offline
`tests/integration/test_mcp_error_sanitization.py` suite from plan 13-03.

### Cost

Always Free VM shapes (`VM.Standard.A1.Flex` up to 4 OCPU / 24GB total across
all A1 instances, or `VM.Standard.E2.1.Micro` x2) plus up to 200GB of block
storage are $0/month for the lifetime of the account, not a time-limited
trial. A Free Tier account cannot be charged unless explicitly converted to
Pay As You Go; the card on file at signup is identity verification only.

### Teardown

```
oci compute instance terminate --instance-id <instance-id> --preserve-boot-volume false
```

## Appendix: Hugging Face Spaces (alternative, requires HF PRO)

**Why not primary:** Docker/Gradio Spaces now require a paid PRO subscription
($9/month) to create; only static (non-Docker) Spaces are free, which cannot
run this project's container. Kept here as a documented, committed
alternative for operators who already have HF PRO.

### Prerequisites

1. Install the HF CLI:
   ```
   uv tool install "huggingface_hub[cli]"
   ```
2. Create an account at https://huggingface.co/join if you do not have one,
   and an active PRO subscription.
3. Authenticate:
   ```
   hf auth login
   ```
   Paste a User Access Token (write scope) from
   https://huggingface.co/settings/tokens.

### Create the Space

1. Create a new Docker Space. The web UI at https://huggingface.co/new-space
   (SDK: Docker, visibility: Public) is the most reliable path. The CLI
   equivalent, confirmed against the installed `hf` binary's `--help`:
   ```
   hf repo create <owner>/poc-scraper-mcp --type space --sdk docker --public
   ```
   If `poc-scraper-mcp` is taken, pick the closest available variant and keep
   this runbook's example commands, the README, and `MCP_PUBLIC_HOSTNAME`
   consistent with the name you actually got (D-04 app-identity intent).
2. Note the exact `<owner>/<space-name>` slug; it is the argument to every
   command below.

### Configure secrets and variables

In the Space's Settings page (`https://huggingface.co/spaces/<owner>/<space-name>/settings`),
under "Variables and secrets":

1. Add a **Secret** named `EXA_API_KEY` with your Exa key (from your local
   `.env` or the exa.ai dashboard). `Settings.mcp_tier` raises at startup
   without it, so the container crash-loops if this is missing.
2. Add a **Variable** (non-secret) named `MCP_PUBLIC_HOSTNAME`. Its value is
   the Space's direct URL hostname, shown at the top of the Space page once
   the first build completes (do not assume the `<owner>-<space-name>.hf.space`
   naming convention holds for every namespace; confirm the real hostname).

Both Secrets and Variables are injected into the container as environment
variables, the same mechanism `fly secrets set` uses for Fly.

### Push the build context

```
uv run python -m scripts.push_hf_space <owner>/<space-name>
```

or via the Makefile wrapper:

```
make deploy-hf HF_SPACE=<owner>/<space-name>
```

`scripts/push_hf_space.py` copies an explicit allowlist, exactly what the
Dockerfile's `COPY` instructions need (`Dockerfile`, `pyproject.toml`,
`uv.lock`, `.dockerignore`, `src/`, `evals/`, `configs/`), plus the Space card
at `deploy/hf-space/README.md`, into a scratch directory and uploads it with
`hf upload` (a single-commit upload, not `git push`). Nothing else, no
`.env`, `credentials.json`, `.planning/`, `tests/`, or this project's own
top-level `README.md`, ever leaves the working tree. This mirrors the
`.dockerignore` discipline the local Docker build already applies, made
explicit because the Space repo is pushed as its own tree rather than
filtered by `docker build`.

### app_port and the container

Docker Spaces route external traffic to the port declared as `app_port` in
the Space card's YAML front matter (`deploy/hf-space/README.md`). It is set
to `8000` here, matching the Dockerfile's `EXPOSE 8000` and the server's
default `MCP_HTTP_PORT`. `MCP_HTTP_HOST` is already `0.0.0.0` in the
Dockerfile's `ENV`. If the internal port ever changes, update `app_port` in
`deploy/hf-space/README.md` to match.

### Single-instance and idle behavior (mapping D-01/D-03)

Free CPU-basic Spaces run exactly one container replica; there is no scale
knob to misconfigure, so the `DemoLimiter`'s in-memory counters are globally
correct by construction. This satisfies the same single-machine intent as
Fly's `fly scale count 1` pin, without a separate pinning step.

Free Spaces sleep after a period of inactivity (Hugging Face documents this
as roughly 48 hours for free-tier Spaces, subject to change) and cold-start
on the next request. The in-memory `DemoLimiter` counters reset on that
restart, the same accepted tradeoff as Fly's suspend/restart behavior (see
"Idle behavior and cost" in the Fly appendix below). Expect the first request
after a sleep period to take noticeably longer while the container restarts;
subsequent requests return at normal latency.

### Verifying the deploy

Replace `<space-hostname>` with the confirmed hostname from the Space page.

1. Confirm the MCP endpoint responds to a JSON-RPC initialize call:
   ```
   curl -sS -X POST https://<space-hostname>/mcp \
     -H "Accept: application/json, text/event-stream" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"deploy-check","version":"0.1"}}}'
   ```
   Expect a non-421, non-5xx response. A 421 means the `Host` header did not
   match the `TransportSecuritySettings` allowlist; confirm the `Variable`
   `MCP_PUBLIC_HOSTNAME` matches the real Space hostname exactly.
2. Check the Space's build/container logs (Space page, "Logs" tab) for the
   startup lines: the resolved tier line must say `thin`, and the demo-limits
   line must show the 5/25/5 defaults.

### Cost

Docker Spaces on `cpu-basic` require an active PRO subscription ($9/month).
This is why the primary hosted target moved to Oracle Cloud Always Free.

### Teardown

Delete the Space from its Settings page, or:
```
hf repo delete <owner>/<space-name> --type space
```

## Appendix: Fly.io (alternative, requires a card on file)

Fly.io's artifacts (`Dockerfile` is shared with the other targets above,
`fly.toml`) stay committed as a documented alternative for operators who
already have Fly billing configured. `fly apps create` now requires a
payment method on the account before it will create an app, even though the
resulting usage can stay within Fly's free allowances; this blocked the live
deploy for this milestone's operator, and the subsequent HF Spaces attempt
hit the same class of payment gate (PRO required). The commands below were
validated through the plan 13-02/13-03 dry run and app-creation attempt but
were not carried through a live deploy.

### Dry run findings

Before authoring the Dockerfile and `fly.toml`, the roadmap required an early
`fly launch` dry run to falsify or confirm the deploy-mechanics assumptions in
`13-RESEARCH.md` (Assumptions A1-A3, Open Questions 1-2, Pitfalls 1-2). This
section records what that dry run found in this execution environment.

**flyctl install:** `flyctl` was not present, so it was installed via
`brew install flyctl`. `fly version` reports:

```
fly v0.4.71 darwin/arm64 Commit: 56c828f79ca41a154d5983e22b90725da37e44f5 BuildDate: 2026-07-14T14:30:51Z
```

**Authentication (plan 13-02 dry run):** `fly auth whoami` returned
`Error: no access token available. Please login with 'flyctl auth login'`.
No Fly.io account or API token was available in that execution environment.
Per the plan's documented fallback for this exact case, the run degraded
gracefully: the Dockerfile and `fly.toml` are authored directly from the
`13-PATTERNS.md`/`13-RESEARCH.md` excerpts rather than from a generated
`fly launch` config.

**Authentication and app creation (plan 13-04):** `fly auth login` succeeded
in a later session (an authenticated account was available). `fly apps
create poc-scraper-mcp` then failed with "We need your payment information".
No Fly app exists as a result; this is the deviation documented at the top of
this file.

**Observations, confirmed or deferred:**

1. **App name availability (`poc-scraper-mcp`).** Not confirmed; blocked by
   the payment-method requirement above.
2. **Generated `fly.toml` content.** Not confirmed, no authenticated
   `fly launch` could complete. `fly.toml` in this repo is hand-authored from
   `13-RESEARCH.md` Pattern 4 instead of diffed against a generated file.
3. **Smoke-checks flag spelling.** CONFIRMED without authentication: both
   `fly launch --help` and `fly deploy --help` list an identical boolean
   flag:
   ```
   --smoke-checks   Perform smoke checks during deployment (default true)
   ```
   `make deploy-fly` and this appendix use `fly deploy --smoke-checks=false`,
   confirming RESEARCH Pitfall 1 (the MCP JSON-RPC endpoint does not answer a
   generic smoke check GET usefully).
4. **Machine-count key in generated `fly.toml`.** Not directly confirmed.
   Indirectly corroborated: `fly.toml`'s schema, per `13-RESEARCH.md`'s
   citation of Fly's own configuration reference, has no dedicated
   machine-count key. This repo's `fly.toml` deliberately omits any
   machine-count field; the one-machine pin is `fly scale count 1`, run once
   after the first authenticated deploy (see "Single-machine pin" below).
5. **Machine count for a freshly launched, undeployed app (`fly status`).**
   Not confirmed; blocked by the payment-method requirement above.

**Summary:** 1 observation (the smoke-checks flag) was confirmed directly
against the installed `flyctl` binary without requiring authentication. App
creation itself is blocked on this account by Fly's payment-method
requirement, so this appendix's remaining steps are documented but unverified
by a live deploy in this milestone.

### Prerequisites

1. Install `flyctl`:
   ```
   brew install flyctl
   ```
2. Authenticate:
   ```
   fly auth login
   ```
3. Add a payment method to the Fly.io account (required by Fly as of this
   writing, even for usage that stays within free allowances):
   https://fly.io/dashboard/personal/billing
4. Docker Engine is recommended for local builds and for the iterative
   dry-run loop (faster than a remote build on every change). If Docker is
   unavailable, `fly deploy` falls back to Fly's remote builder:
   ```
   fly deploy --remote-only
   ```

### First deploy

```
fly launch --no-deploy
```
Reconcile the generated app name and `MCP_PUBLIC_HOSTNAME` in `fly.toml` if
the name differs from `poc-scraper-mcp`.

1. Set the only secret this server needs. `EXA_API_KEY` is never baked into
   the image or `fly.toml`; it is delivered as a Fly secret at runtime:
   ```
   fly secrets set EXA_API_KEY=<your-exa-key>
   ```
2. Deploy:
   ```
   make deploy-fly
   ```

### Single-machine pin

The in-memory `DemoLimiter` rate-limit counters (per-IP hourly window,
UTC-day global cap) are only globally correct if exactly one machine process
holds them. `fly.toml` has no dedicated machine-count key, so this pin is an
operational step, not a config value:

1. After the first deploy, run:
   ```
   fly scale count 1
   ```
2. Verify with both:
   ```
   fly status
   fly scale show
   ```
   Confirm exactly one machine exists in exactly one region.

**Warning:** never run `fly scale count` with a value higher than 1, and
never add a second region. Either action silently fragments the in-memory
rate-limit counters into per-machine limits, multiplying the effective daily
cap with no code-level warning. This must never be done.

### Idle behavior and cost

`fly.toml` sets `auto_stop_machines = "suspend"` (not `"stop"`, not
always-on). Auto-suspend freezes the VM's memory on idle and restores it on
wake, so the in-memory `DemoLimiter` counters survive quiet periods. Counters
reset only on deploys or crashes, an accepted tradeoff for a demo-mode
endpoint.

With `shared-cpu-1x`, 256MB, one machine, and suspend-on-idle, expected
realistic spend is under 1-2 USD per month, with a ceiling of about 5 USD per
month even under sustained traffic. This estimate assumes a payment method is
already on file; it does not account for the account-level requirement that
blocked this milestone's live deploy.

### Verifying the deploy

Replace `<app-hostname>` with the confirmed app hostname (for example
`poc-scraper-mcp.fly.dev`).

1. Confirm HTTPS is enforced (`force_https = true`):
   ```
   curl -sI http://<app-hostname>/mcp
   ```
   Expect a redirect to `https://`.
2. Confirm the MCP endpoint responds to a JSON-RPC initialize call:
   ```
   curl -sS -X POST https://<app-hostname>/mcp \
     -H "Accept: application/json, text/event-stream" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"deploy-check","version":"0.1"}}}'
   ```
   Expect a non-421 response (a 421 means the `Host` header did not match the
   `TransportSecuritySettings` allowlist; see "MCP_PUBLIC_HOSTNAME" above).

   This exact request shape was validated locally in plan 13-02 against a
   container built from this repo's Dockerfile: without `MCP_PUBLIC_HOSTNAME`
   set, the container refuses to start; with it set and a matching `Host`
   header, the request returns a 200 with the server's `initialize`
   response, and a request carrying the bind address as `Host` still gets a
   421.

### Teardown

```
fly apps destroy <app-name>
```
