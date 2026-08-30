# Create a scoped Proxmox API token

Run these on the Proxmox host (or any node with `pveum` available). This guide
starts with the built-in read-only `PVEAuditor` role because the chat tool set
in the later steps is deliberately read-only.

```bash
pveum user add mcp-agent@pve
pveum user token add mcp-agent@pve mcp-token --privsep 1
pveum acl modify / -token 'mcp-agent@pve!mcp-token' -role PVEAuditor
pveum acl modify / -user mcp-agent@pve -role PVEAuditor
```

The `pveum user token add` command prints a token value **once** — save it
immediately. It can't be retrieved again; you would have to regenerate it.

## Privilege notes

- Proxmox API-token permissions are always a subset of the backing user's
  permissions. With `--privsep 1`, both the user and token ACLs matter; the
  commands above grant the same read-only role to each. Verify the result:

  ```bash
  pveum user permissions mcp-agent@pve
  pveum user token permissions mcp-agent@pve mcp-token
  ```

  See Proxmox's official
  [Administration Guide](https://pve.proxmox.com/pve-docs/pve-admin-guide.pdf),
  section "Limited API Token for Monitoring", for the
  permission-intersection model.

- `PVEAuditor` intentionally does not grant VM power, disk configuration,
  snapshot, console, or syslog privileges. Some read-only ProxmoxMCP-Plus
  tools will therefore return permission errors. Add only the exact extra
  privileges required for a chosen tool after reviewing the upstream
  [API & Tool Reference](https://github.com/RekklesNA/ProxmoxMCP-Plus/blob/main/docs/wiki/API%20%26%20Tool%20Reference.md).
- Open WebUI's Function Name Filter List controls which schemas the model can
  see. It is not an authorization boundary. Proxmox RBAC remains the backend
  enforcement layer if another authenticated MCP client calls a tool directly.

## What you should have afterwards

- A token ID in the form `mcp-agent@pve!mcp-token`
- A token value (a UUID-like string) — this goes only in
  `auth.token_value` in the ProxmoxMCP-Plus config. Treat it like a password:
  don't commit it anywhere, including this repo if you fork it for your own
  notes.

Do not confuse the Proxmox token value with the two independent frontend
secrets created later:

| Secret | What it protects |
|---|---|
| `auth.token_value` | Authentication from ProxmoxMCP-Plus to Proxmox VE |
| `MCP_API_KEY` | Bearer authentication for native MCP HTTP on port `8000` |
| `PROXMOX_API_KEY` | Bearer authentication for the OpenAPI bridge on port `8811` |
