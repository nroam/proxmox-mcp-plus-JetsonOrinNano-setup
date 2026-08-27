# Build and run ProxmoxMCP-Plus

ProxmoxMCP-Plus can run two ways: as a native MCP Streamable HTTP server, or
as an OpenAPI/REST bridge over the same tools. **Run both** — the MCP server
is what Open WebUI's chat actually uses; the OpenAPI bridge is invaluable for
testing individual tools with plain `curl` while you debug, independent of
the LLM.

## 1. Clone and patch the source

```bash
git clone https://github.com/RekklesNA/ProxmoxMCP-Plus.git
cd ProxmoxMCP-Plus
```

ProxmoxMCP-Plus's built-in tool descriptions use placeholder example node
names (`pve`, `pve1`, `proxmox-node2`) in things like:

```
node* - Host node name (e.g. 'pve')
```

Small local models have a strong tendency to copy these literally into tool
calls instead of treating them as illustrative — i.e. the model will
confidently call a tool with `node="pve"` even when your actual node is
called something else entirely, because that's what the tool's own
description told it to expect. This causes hostname-lookup failures that
are genuinely confusing to debug, because the API token, network, and MCP
protocol are all working fine — the LLM is just passing a wrong parameter
value it got from the tool schema itself.

**Fix**: patch these examples to use your real node names before building.
[`scripts/patch_tool_descriptions.py`](../scripts/patch_tool_descriptions.py)
in this repo does this — copy it into the cloned repo and run it:

```bash
cp /path/to/this/repo/scripts/patch_tool_descriptions.py .
python3 patch_tool_descriptions.py node1 node2 node3   # your real node names
```

It's a safe, mechanical find-and-replace across the source tree for the
`pve`/`pve1`/`pve2`/`proxmox-node2` placeholder tokens specifically (using
word boundaries, so it won't touch unrelated strings like `pveproxy` or
`pvedaemon`, which are Proxmox service names). Review the diff (`git diff`)
before building — it's your own patch, and worth a sanity check.

This alone won't make tool selection perfect (see
[troubleshooting](06-troubleshooting.md#tool-selection-quality)), but it
removes an entire, very confusing class of failure.

## 2. Reset anything that isn't your patch

If you experiment with the `Dockerfile` or `docker-compose.yml` while
debugging (many guides suggest editing `ENV` defaults directly), reset them
before your final build:

```bash
git checkout -- Dockerfile docker-compose.yml
```

See [troubleshooting](06-troubleshooting.md#baked-in-env-vars) for why this
matters — a baked-in `ENV` override in the image can leak into both run
modes and break one of them in a very non-obvious way.

## 3. Build

```bash
docker build -t proxmoxmcp-plus:local .
```

## 4. Config file

Create `config.json` (path is up to you — this guide uses
`~/proxmox-mcp/config.json`):

```json
{
  "mcp": { "transport": "STDIO", "host": "127.0.0.1", "port": 8000 },
  "proxmox": { "host": "<PROXMOX_HOST_IP>", "port": 8006, "verify_ssl": false },
  "auth": {
    "user": "mcp-agent@pve",
    "token_name": "mcp-token",
    "token_value": "<YOUR_TOKEN_VALUE>"
  },
  "jobs": { "sqlite_path": "/app/proxmox-jobs.sqlite3" },
  "security": { "dev_mode": true }
}
```

Notes:

- `verify_ssl: false` + `security.dev_mode: true` are needed if your Proxmox
  host uses its default self-signed certificate. If you have a real cert,
  set `verify_ssl: true` and drop `dev_mode`.
- **`mcp.transport: STDIO` is deliberate and important** — leave it as-is.
  This file gets mounted into *both* containers below; `STDIO` is what the
  OpenAPI bridge's internal subprocess needs. The MCP-HTTP container
  overrides this via its own environment variable instead (next step), so
  the two containers don't conflict despite sharing this file. See
  [troubleshooting](06-troubleshooting.md#shared-config-transport) if you're
  tempted to change it — it's a trap.

## 5. Run both services

```bash
export PROXMOX_API_KEY=$(openssl rand -hex 32)   # for the OpenAPI bridge
export MCP_API_KEY=$(openssl rand -hex 32)        # for the MCP server

docker run -d --name proxmox-mcp-http --restart unless-stopped \
  -p 8000:8000 \
  -e PROXMOX_MCP_MODE=mcp-http \
  -e MCP_HOST=0.0.0.0 -e MCP_PORT=8000 \
  -e MCP_TRANSPORT=STREAMABLE_HTTP \
  -e MCP_API_KEY="$MCP_API_KEY" \
  -v /path/to/config.json:/app/proxmox-config/config.json:ro \
  proxmoxmcp-plus:local

docker run -d --name proxmox-mcp-openapi --restart unless-stopped \
  -p 8811:8811 \
  -e PROXMOX_API_KEY="$PROXMOX_API_KEY" \
  -v /path/to/config.json:/app/proxmox-config/config.json:ro \
  proxmoxmcp-plus:local
```

Save `$PROXMOX_API_KEY` and `$MCP_API_KEY` somewhere durable (a local `.env`
file, `chmod 600`, not committed anywhere) — you'll need both again for the
Open WebUI wiring step.

## 6. Verify

```bash
# OpenAPI bridge — should return {"status":"ok"}
curl -s http://localhost:8811/livez

# A real tool call, authenticated
curl -s -X POST -H "Authorization: Bearer $PROXMOX_API_KEY" \
  -H "Content-Type: application/json" -d '{}' \
  http://localhost:8811/get_nodes
```

If that returns real node data, the server side is solid — any problems
from here on are in the Open WebUI / LLM integration, not this layer. Keep
this `curl` command handy; it's the fastest way to tell "is this a wiring
bug" from "is this an LLM reasoning bug" throughout the rest of setup.
