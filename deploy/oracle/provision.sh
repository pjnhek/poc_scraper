#!/usr/bin/env bash
# Provision an Oracle Cloud Always Free compute instance for poc-scraper-mcp.
#
# Prerequisites (see docs/DEPLOY.md "Oracle Cloud Always Free"):
#   - oci CLI installed and authenticated (`oci session authenticate`, or an
#     API-key config profile at ~/.oci/config).
#   - A VCN with a public subnet (internet gateway + route table + a security
#     list that will later be opened for 443). The OCI console's "Create VCN
#     with Internet Connectivity" wizard is the fastest one-time path for a
#     first VM; this script only launches the instance, not the network.
#
# Required env vars:
#   OCI_COMPARTMENT_ID   compartment OCID to launch into
#   OCI_AD               availability domain, e.g. from:
#                         oci iam availability-domain list \
#                           --compartment-id "$OCI_COMPARTMENT_ID"
#   OCI_SUBNET_ID         subnet OCID with internet connectivity
# Optional:
#   SSH_PUBLIC_KEY_FILE   default ~/.ssh/id_rsa.pub
#   INSTANCE_NAME         default poc-scraper-mcp (D-04 app-identity intent)
#   REPO_URL              forwarded to setup.sh; default this repo's GitHub URL
#
# Tries the Always Free ARM shape first (VM.Standard.A1.Flex, 1 OCPU / 6GB),
# falling back to the Always Free AMD shape (VM.Standard.E2.1.Micro) if the
# ARM shape reports a capacity/limit error in this availability domain. This
# is the documented Always Free capacity gotcha: A1.Flex has finite per-AD
# capacity that regularly runs out; E2.1.Micro is the smaller but always
# obtainable fallback.

set -euo pipefail

: "${OCI_COMPARTMENT_ID:?Set OCI_COMPARTMENT_ID (see docs/DEPLOY.md)}"
: "${OCI_AD:?Set OCI_AD (see docs/DEPLOY.md)}"
: "${OCI_SUBNET_ID:?Set OCI_SUBNET_ID (see docs/DEPLOY.md)}"

SSH_PUBLIC_KEY_FILE="${SSH_PUBLIC_KEY_FILE:-$HOME/.ssh/id_rsa.pub}"
INSTANCE_NAME="${INSTANCE_NAME:-poc-scraper-mcp}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$SSH_PUBLIC_KEY_FILE" ]; then
  echo "No SSH public key at $SSH_PUBLIC_KEY_FILE (set SSH_PUBLIC_KEY_FILE)" >&2
  exit 1
fi

find_image() {
  local shape="$1"
  oci compute image list \
    --compartment-id "$OCI_COMPARTMENT_ID" \
    --operating-system "Canonical Ubuntu" \
    --operating-system-version "22.04" \
    --shape "$shape" \
    --sort-by TIMECREATED --sort-order DESC \
    --query 'data[0].id' --raw-output 2>/dev/null
}

launch() {
  local shape="$1"
  shift
  local image_id
  image_id="$(find_image "$shape")"
  if [ -z "$image_id" ] || [ "$image_id" = "null" ]; then
    echo "No Ubuntu 22.04 image found for shape $shape" >&2
    return 1
  fi
  oci compute instance launch \
    --compartment-id "$OCI_COMPARTMENT_ID" \
    --availability-domain "$OCI_AD" \
    --subnet-id "$OCI_SUBNET_ID" \
    --shape "$shape" \
    "$@" \
    --display-name "$INSTANCE_NAME" \
    --image-id "$image_id" \
    --assign-public-ip true \
    --metadata "{\"ssh_authorized_keys\":\"$(cat "$SSH_PUBLIC_KEY_FILE")\"}" \
    --user-data-file "$SCRIPT_DIR/setup.sh" \
    --wait-for-state RUNNING
}

echo "Attempting VM.Standard.A1.Flex (1 OCPU / 6GB, Always Free ARM shape)..."
if launch VM.Standard.A1.Flex --shape-config '{"ocpus":1,"memoryInGBs":6}'; then
  echo "Launched on VM.Standard.A1.Flex."
else
  echo "A1.Flex unavailable in $OCI_AD (capacity or per-AD limit)." >&2
  echo "Falling back to VM.Standard.E2.1.Micro (smaller Always Free shape)..." >&2
  launch VM.Standard.E2.1.Micro
  echo "Launched on VM.Standard.E2.1.Micro. setup.sh adds swap to compensate for the lower RAM."
fi

cat <<'EOF'

Instance is launching. Find its public IP once it is RUNNING:
  oci compute instance list --compartment-id "$OCI_COMPARTMENT_ID" \
    --display-name poc-scraper-mcp --query 'data[0].id' --raw-output
  oci compute instance list-vnics --instance-id <instance-id> \
    --query 'data[0]."public-ip"' --raw-output

setup.sh already ran once as the instance's boot user-data. It wrote
/opt/poc-scraper/mcp.env with a placeholder EXA_API_KEY. SSH in, edit that
file, then re-run setup.sh to pick it up (see docs/DEPLOY.md).
EOF
