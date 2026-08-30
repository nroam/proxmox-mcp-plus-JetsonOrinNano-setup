# Wire ProxmoxMCP-Plus into Open WebUI

## 1. Run Open WebUI

```bash
export WEBUI_SECRET_KEY=$(openssl rand -hex 32)

docker run -d --name open-webui --restart always \
  --network host \
  -e PORT=3000 \
  -e OLLAMA_BASE_URL=http://127.0.0.1:11434 \
  -e WEBUI_SECRET_KEY="$WEBUI_SECRET_KEY" \
  -v open-webui:/app/backend/data \
  ghcr.io/open-webui/open-webui:0.11.1
```

Notes:

- **`--network host`**, not a published port mapping. Ollama is bound to
  `127.0.0.1` by default; a container on the default bridge network can't
  reach that. Host networking sidesteps the whole problem.
- **Pin a specific version tag**, don't use `:main`. We tested against both
  `:main` and the `0.11.1` stable release and hit the same tool-calling bug
  (below) on both — pinning doesn't fix that specific issue, but it does
  make your setup reproducible, which matters a lot when you're debugging
  LLM flakiness and want to rule out "did the container just update under
  me" as a variable.
- Save `WEBUI_SECRET_KEY` in the same protected local `.env` file as the other
  service secrets before recreating the container. A stable key is required
  for encrypted Open WebUI state, especially if you later use OAuth-backed
  MCP connections.
- First boot takes 30-60 seconds (downloads an embedding model). Poll
  `curl http://localhost:3000/` until you get a `200`.

Go to `http://<jetson-ip>:3000`, complete the first-run signup (this becomes
your admin account). Restrict port `3000` to your trusted LAN; use HTTPS and an
authenticated reverse proxy before allowing access from any untrusted network.

## 2. Register ProxmoxMCP-Plus as a tool server

**Admin Panel → Settings → Integrations → External Tool Servers → add (+)**

| Field | Value |
|---|---|
| Type | **MCP Streamable HTTP** |
| URL | `http://127.0.0.1:8000/mcp` |
| Auth | Bearer, using the `MCP_API_KEY` from the previous doc |

**This detail matters for this tested stack**: Open WebUI officially supports
both OpenAPI tool servers and MCP Streamable HTTP, but the author observed that
the OpenAPI connection passed "Test Connection" and still was not invoked by
chat completions on this Open WebUI `0.11.1` + Ollama setup. Native MCP
Streamable HTTP was verified end-to-end and is therefore the recommended path
for this guide. Do not treat the observation as a statement that OpenAPI tools
never work in other Open WebUI environments. Full diagnosis:
[troubleshooting](06-troubleshooting.md#openapi-vs-mcp).
For the supported connection types, compare Open WebUI's official
[MCP documentation](https://docs.openwebui.com/features/extensibility/mcp/)
and
[OpenAPI integration documentation](https://docs.openwebui.com/features/extensibility/plugin/tools/openapi-servers/open-webui/).

## 3. Curate the exposed tools

In the same connection's settings, use **Function Name Filter List** to
restrict which tools the chat model can see and call. This is a
comma-separated **allow-list**.

Two reasons to curate rather than exposing everything:

1. **Safety.** ProxmoxMCP-Plus exposes plenty of mutating tools (create/
   delete/start/stop VMs and containers, snapshots, backups,
   `execute_vm_command`). A small model with imperfect judgement is not
   somewhere you want unrestricted write access by default. Start with
   read-only tools only; add specific mutating tools back deliberately, one
   at a time, once you trust the setup.
2. **Reliability.** A 7B-class model's tool-selection accuracy degrades
   noticeably as the tool count grows. We found ~50 tools caused the model
   to essentially never call anything useful; a curated set in the 10-20
   range was materially more reliable. See
   [troubleshooting](06-troubleshooting.md#tool-selection-quality) for the
   detail on what we tried.

The filter limits the schemas shown to the model; it does not change the tools
registered by ProxmoxMCP-Plus and is not an authorization control. Keep the
Proxmox API token read-only unless you deliberately need mutations, and keep
`MCP_API_KEY` private.

A reasonable read-only starting set (adjust names to match your
ProxmoxMCP-Plus version):

```
get_nodes,get_node_status,get_storage,get_cluster_status,get_vms,get_vm_config,get_containers,get_container_config,get_container_ip,list_isos,list_templates,list_backups,list_jobs,get_job,poll_job
```

Tools that require both a `node` and a `vmid`/`upid` parameter (config
lookups, snapshot listing, per-guest logs) are more prone to the model
guessing wrong values than tools that take no parameters or just a node —
worth being aware of as you decide what to add.

## 4. Model configuration

**Admin Panel → Settings → Models**, edit your model
(`qwen2.5:7b-instruct-q4_K_M`):

- **Tools**: enable your ProxmoxMCP-Plus connection as a default tool for
  this model (so you don't have to toggle it on manually every chat).
- **Advanced Params → Function Calling: `Legacy`, not `Native`.** This was
  the single most impactful setting on the tested Open WebUI `0.11.1` +
  Ollama `0.32.14` stack. In that environment, native function calling had a
  bug where, after a tool call
  completes, the model's synthesized final answer is silently dropped —
  the tool call visibly succeeds (you see "View Result from ...") but the
  chat response is empty. This reproduced consistently across multiple
  models and Open WebUI versions; direct testing against Ollama's own API
  (bypassing Open WebUI entirely) confirmed Ollama itself returns a
  complete, correct response every time — so it's specifically Open WebUI's
  handling of the native tool-calling response stream. **Legacy mode
  (prompt-based tool calling) did not have this problem in the author's
  tests.** It has its own, milder weakness — see the troubleshooting doc.
  Re-test Native mode after upgrades rather than assuming this workaround is
  permanent. Open WebUI documents both modes and describes Legacy as a
  compatibility option in its
  [tool-calling documentation](https://docs.openwebui.com/features/extensibility/plugin/tools/).
- **System Prompt**: see the template below.

## 5. System prompt

A generic template — fill in your real node names and adjust the tool list
to match what you exposed in step 3:

```
You are a Proxmox VE assistant with direct access to live cluster data via
tools. The real nodes in this cluster are <NODE1>, <NODE2>, and <NODE3> —
these are the ONLY valid node names. Any "e.g." example in a tool
description is just an example, not a literal value to use.

Available tools and what each does:
- get_nodes() — no params. List all nodes with status/CPU/memory.
- get_vms() — no params. All VMs cluster-wide with status.
- get_containers() — no params. All containers cluster-wide with status.
[... one line per tool you've exposed, noting required params ...]

Rules:
1. Pick the ONE tool most directly relevant to the question. Most general
   status questions are fully answered by get_vms or get_containers alone
   — do not chain into logs or per-guest detail unless the user asks for
   that specifically, or the first result shows a clear problem needing it.
2. Never guess a node name — only use one returned by get_nodes or an
   earlier tool result in this conversation.
3. If a tool call fails or returns a permission error, do not retry with
   different guessed parameters and do not try to debug the error —
   briefly note the detail was unavailable and answer with what you have.
4. Answer using only the data actually returned. Never guess or claim you
   lack access when a relevant tool exists.
```

The per-tool descriptions matter more than they might seem — the model
weighs the tool's own schema description more heavily than prose elsewhere
in the system prompt for deciding *whether* to call it, but weighs the
system prompt's explicit rules more heavily for deciding *what parameters*
to pass and *whether to stop*. Both mattered in testing.

## 6. Verify

Ask something the model can answer from a single, parameterless tool call
first — e.g. "what nodes are in the cluster?" — before trying anything more
open-ended. If that doesn't work, you have a wiring problem; work through
[troubleshooting](06-troubleshooting.md) rather than tuning the prompt
further.
