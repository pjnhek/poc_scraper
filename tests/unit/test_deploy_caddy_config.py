"""Guard the Oracle Caddy proxy's client-IP trust boundary.

src/mcp_server/limits.py trusts the Fly-Client-IP header verbatim as the
rate-limit bucket key. That is only safe if the fronting proxy overwrites any
client-supplied value with the real peer. Caddy does not strip arbitrary
inbound headers by default, so the setup.sh Caddyfile MUST set Fly-Client-IP
from {remote_host}. This is a config-layer invariant no app-level test can
reach; assert it against the committed deploy script so it cannot be silently
removed.
"""

from __future__ import annotations

import re
from pathlib import Path

SETUP_SH = Path(__file__).resolve().parents[2] / "deploy" / "oracle" / "setup.sh"


def _caddyfile_heredoc() -> str:
    text = SETUP_SH.read_text()
    match = re.search(r"cat >/etc/caddy/Caddyfile <<EOF\n(.*?)\nEOF", text, re.DOTALL)
    assert match is not None, "setup.sh no longer writes a Caddyfile heredoc"
    return match.group(1)


def test_caddy_overwrites_fly_client_ip_from_real_peer() -> None:
    caddyfile = _caddyfile_heredoc()
    assert "header_up Fly-Client-IP {remote_host}" in caddyfile, (
        "Caddy must overwrite client-supplied Fly-Client-IP with the real peer; "
        "without it the per-IP rate limit is spoofable (limits.py trusts this header)"
    )


def test_caddy_reverse_proxies_only_to_loopback() -> None:
    caddyfile = _caddyfile_heredoc()
    assert "reverse_proxy 127.0.0.1:8000" in caddyfile
