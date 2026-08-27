# Create a scoped Proxmox API token

Run these on the Proxmox host (or any node with `pveum` available), replacing
placeholders as noted.

```bash
# A role covering read-only inventory/status/logs plus (optionally) common
# power-management actions. Start read-only-only if you're cautious — see
# note below.
pveum role add MCP-Operator -privs \
  "VM.Audit VM.PowerMgmt VM.Config.Disk VM.Snapshot Datastore.Audit Sys.Audit"

pveum user add mcp-agent@pve

pveum acl modify / -user mcp-agent@pve -role MCP-Operator

pveum user token add mcp-agent@pve mcp-token --privsep 0
```

The last command prints a token value **once** — save it immediately, it
can't be retrieved again (you'd have to regenerate it).

## Privilege notes

- `--privsep 0` disables privilege separation for the token, meaning it
  inherits the full privileges of the role granted at `/`. This is simpler
  for a single-purpose assistant token; if you want tighter scoping, look
  into Proxmox's token privilege separation instead.
- **Start minimal.** The role above deliberately excludes anything that lets
  the token read syslogs or guest firewall logs (`Sys.Syslog`, `VM.Console`).
  If you want the assistant to have access to those tools, add them later:

  ```bash
  pveum role modify MCP-Operator -privs \
    "VM.Audit VM.PowerMgmt VM.Config.Disk VM.Snapshot Datastore.Audit Sys.Audit Sys.Syslog VM.Console"
  ```

  Be aware `VM.Console` grants interactive console *viewing* access, not
  just log reading — it's a meaningfully bigger grant than "read logs"
  implies, because Proxmox's guest firewall-log API endpoint happens to
  check this privilege rather than a narrower audit-only one.
- If you only want the assistant to answer questions (no VM/container
  power actions even in principle), drop `VM.PowerMgmt` — the tool-level
  curation in [`05-open-webui-wiring.md`](05-open-webui-wiring.md) is what
  actually controls what the *chat* can invoke, but keeping the underlying
  token's privileges minimal too is defense in depth.

## What you should have afterwards

- A token ID in the form `mcp-agent@pve!mcp-token`
- A token value (a UUID-like string) — this is your `PROXMOX_API_KEY` /
  `token_value` for the next steps. Treat it like a password: don't commit
  it anywhere, including this repo if you fork it for your own notes.
