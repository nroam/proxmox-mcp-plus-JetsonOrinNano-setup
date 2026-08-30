# Troubleshooting

Organized roughly in the order you're likely to hit these while working
through the setup docs. Each section notes how to tell "is this actually my
problem" before you spend time on a fix that doesn't apply.

## General debugging technique

Throughout setup, keep three layers separate in your head, and test them
independently when something's not working:

1. **Is the backend right?** `curl` the OpenAPI bridge directly (see the end
   of [`03-build-proxmoxmcp-plus.md`](03-build-proxmoxmcp-plus.md)). If this
   works, Proxmox connectivity, auth, and the MCP server itself are fine.
2. **Is the wiring right?** Is Open WebUI's tool server actually being
   invoked for a real chat request? (See [OpenAPI vs MCP](#openapi-vs-mcp)
   below — a green "Test Connection" does not guarantee this.)
3. **Is the LLM making good decisions?** Given correct data reaching it, is
   it calling the right tool with the right arguments, and producing a
   sensible final answer?

Nearly every confusing symptom in this guide turned out to be layer 2 or 3
disguising itself as something else. Rule out layer 1 first (it's the
fastest to check and, once your config is right, is extremely reliable) —
if a direct `curl` to the bridge works perfectly, stop suspecting Proxmox,
the network, or your API token, and look upstream in the chain instead.

---

## OpenAPI vs MCP

**Symptom**: tool server shows "Connection success" in Open WebUI, tool
schema is visible, but chat responses never actually call any tool — the
model just says it doesn't have access, or hallucinates an answer.

**Observed cause on the tested stack**: Open WebUI supports two connection
types for external tool servers — "OpenAPI" and "MCP Streamable HTTP". On
Open WebUI `0.11.1` with the guide's Ollama configuration, only
`server:mcp:`-prefixed tool IDs were observed resolving into a live protocol
client at chat-request time. The OpenAPI connection's tool definitions did not
reach the model even though its schema was fetchable and the connection test
succeeded. Open WebUI officially supports OpenAPI tools, so treat this as a
version- and environment-specific observation rather than a universal product
limitation.

**Workaround verified by the author**: use MCP Streamable HTTP as the
connection type (see
[`05-open-webui-wiring.md`](05-open-webui-wiring.md)), pointed at
ProxmoxMCP-Plus's `mcp-http` mode (port 8000, path `/mcp`), not the OpenAPI
bridge (port 8811).

**How to confirm this is your problem**: enable debug logging
(`-e GLOBAL_LOG_LEVEL=DEBUG` on the Open WebUI container) and grep its logs
for `tool_ids=` and `direct_tool_servers=` /`tool_servers=` around a chat
request. If `tool_ids` shows your connection but the resolved tool servers
list is empty, this is it.

---

## Native function calling

**Tested versions**: Open WebUI `0.11.1`, Ollama `0.32.14`. Re-test after an
upgrade because native tool handling changes frequently.

**Symptom**: a tool call visibly succeeds (you see "View Result from
`<tool>`" with real data), but the chat message that follows is empty. No
error, just nothing.

**Diagnosis path that confirmed this wasn't a backend or model problem**:
we captured the exact request Open WebUI sent to Ollama (system prompt,
full tool schema, the tool-call message and its result) via debug logging,
and replayed it directly against Ollama's own `/api/chat` endpoint — both
streaming and non-streaming, with and without the full tool schema. Every
direct replay produced a complete, correct response. This isolates the bug
to Open WebUI's own handling of the response stream specifically for
native/structured tool calling, not the model or Ollama.

**Workaround verified by the author**: set **Function Calling: Legacy** for
the model in Open WebUI
(Admin Panel → Settings → Models → your model → Advanced Params). Legacy
mode has the model emit tool calls as part of its own text generation
(parsed via prompt template) rather than relying on Ollama's structured
`tool_calls` field, and doesn't hit this bug.

**Trade-off**: legacy mode is weaker at *chaining* — if the model decides,
after seeing a tool result, that it should call a second tool before
answering, it sometimes just describes that intention in text rather than
actually doing it. In practice this is much less disruptive than a
silently empty response.

**Don't try**: disabling streaming (`params.stream_response: false`) as a
workaround for the native-mode bug — we tried this and it made things
worse (the chat UI hangs waiting for a stream that never arrives, since the
frontend's rendering logic still expects one). Revert this if you've set
it; it doesn't fix the underlying issue.

---

## Qwen3 runaway generation

**Symptom**: with a Qwen3 model (tested: 4B and 8B) and tools enabled,
generation runs for many minutes, GPU/CPU stays pegged, and the process
never completes on its own — eventually needs to be killed
(`ollama stop <model>`, or `curl -X POST /api/generate -d
'{"model":"...","keep_alive":0}'`, or as a last resort a service restart if
even that doesn't respond).

**Cause** (best available diagnosis for Ollama `0.32.14` — may be fixed in
newer releases): Ollama substitutes its own generic ChatML
tool-calling template for any request that includes tool definitions,
instead of rendering the model's own bundled Jinja template — visible via
`ollama show <model> --modelfile` (shows the real template) versus the
`--chat-template chatml --no-jinja` flags visible in the running
`llama-server` process's command line
(`ps aux | grep llama-server`). Qwen3's own template encodes its
thinking-mode conventions (`<think>...</think>` blocks) and its specific
`<tool_call>` XML wrapping; the generic substitute doesn't, and the model
appears to never reliably emit whatever token/sequence the runtime is
listening for to stop, especially in combination with `--context-shift`
(which lets generation continue past the nominal context window instead of
erroring out, removing the safety net that would otherwise cap a runaway
generation).

**Fix**: use a Qwen2.x-family model instead (this guide uses
`qwen2.5:7b-instruct-q4_K_M`), or check whether a newer Ollama release has
changed this behavior for Qwen3 specifically before retrying it.

**If you hit a stuck process and need to kill it**: try the graceful path
first (`ollama stop <model>`, or the `keep_alive: 0` API call above) — this
worked in most cases even when the process looked pegged. If that doesn't
respond within a reasonable window, you'll need `sudo systemctl restart
ollama` (or equivalent for your init system).

---

## Memory pressure

**Symptom**: variable, often confusing — slow responses, requests that time
out, or a process that never completes and pegs CPU without using the GPU
(easy to mistake for the Qwen3 issue above, or for a code bug, when it's
actually just the system swapping).

On an 8GB-class Jetson, a 7B-class model at Q4 quantization plus Open WebUI
plus Docker overhead leaves very little headroom — we regularly saw
available memory drop to 150-300MB during generation, and a genuinely stuck
process (from an unrelated bug) held ~5-6GB resident for 40+ minutes before
being noticed, during which every other request on the box was starved.

**How to check**: `free -h` and `ps aux --sort=-%mem | head`. If a
`llama-server` process is resident for far longer than a normal response
should take, and swap usage is climbing, this is your problem regardless of
what the actual symptom looked like.

**Mitigations**:

- Don't run other heavy processes on the box alongside a chat session.
- If you're testing a bigger model than fits comfortably, watch memory
  during the *first* load and first real request specifically — that's
  where thrashing shows up first.
- Consider `OLLAMA_KEEP_ALIVE` tuning if models are staying loaded longer
  than you want between requests (default is a few minutes of idle before
  unload).

---

## Tool-selection quality

**Symptom**: correct data is available, the model has the right tool
available, but it doesn't call it — instead it either answers vaguely, or
reaches for a less relevant tool (e.g. checking system logs in response to
"any issues with my containers?" instead of just listing container
status).

This is a genuine model-reasoning limitation at the 7B-class quantized
scale, not a bug — but it's very sensitive to how many tools are in play
and how they're described. What measurably helped, in order of impact:

1. **Curating the tool set** down from ProxmoxMCP-Plus's full ~50 tools to
   a task-relevant subset (10-20 tools) via Open WebUI's Function Name
   Filter List. This was the single biggest lever.
2. **Removing tools whose built-in example values don't match reality**
   (see the node-name patch in
   [`03-build-proxmoxmcp-plus.md`](03-build-proxmoxmcp-plus.md)) — the
   model was reliably copying misleading examples otherwise.
3. **Excluding tools that require multiple parameters the model has to
   have learned from an earlier step** (`node` + `vmid` together) from the
   default set, since the model would often skip straight to guessing
   rather than chaining a lookup first. Tools requiring at most one
   parameter (or none) were noticeably more reliable.
4. **An explicit, blunt mapping in the system prompt** ("if the question
   mentions containers, your first and usually only tool call is
   `get_containers`") measurably helped but didn't fully eliminate the
   issue on its own — it needed to be combined with the tool-set curation
   above, not used as a substitute for it.

If reliability still isn't good enough for your use case after all of the
above, the remaining lever is a bigger/better model — see the note on model
choice in [`04-ollama-setup.md`](04-ollama-setup.md).

---

## Baked-in env vars

**Symptom**: after editing `Dockerfile` (e.g. to change the default run
mode for convenience) and rebuilding, one of the two ProxmoxMCP-Plus
services breaks in a way that looks unrelated to your edit — e.g. the
OpenAPI bridge stops binding its port, or hangs on startup.

**Cause**: `ENV` directives in a Dockerfile become defaults baked into the
image, inherited by every process the container runs — including the
OpenAPI bridge's internal subprocess, which is a *separate* MCP server
instance talking to its own parent process over stdio. An env var meant to
configure the top-level run mode (e.g. `MCP_TRANSPORT=STREAMABLE_HTTP`,
intended for the `mcp-http` service) leaks into that internal subprocess
too, and causes it to try to bind its own HTTP server instead of speaking
stdio to its parent — breaking the handshake in a way that's easy to
mistake for a completely unrelated bug.

**Fix**: keep `Dockerfile` and `docker-compose.yml` pristine (`git checkout
--` before building), and pass every mode-specific setting explicitly via
`-e` flags at `docker run` time for each container, rather than relying on
image-level defaults.

---

## Shared config transport

**Symptom**: after changing `config.json`'s `mcp.transport` to
`STREAMABLE_HTTP` (e.g. while trying to get the `mcp-http` service working),
the **OpenAPI bridge** breaks — the app builds, starts, but that container
never binds its port.

**Cause**: both containers in this guide mount the same `config.json`
read-only. The OpenAPI bridge relies on its internal subprocess reading
`mcp.transport: STDIO` from that file (it has no other way to know to speak
stdio to its parent rather than starting its own server). The `mcp-http`
service, on the other hand, needs `STREAMABLE_HTTP` — but gets that via its
own `MCP_TRANSPORT` environment variable at `docker run` time (which takes
priority over the file), not by changing the shared file.

**Fix**: leave `config.json`'s `mcp.transport` as `STDIO` always. Set the
`mcp-http` service's actual transport via its `-e MCP_TRANSPORT=
STREAMABLE_HTTP` flag, as shown in
[`03-build-proxmoxmcp-plus.md`](03-build-proxmoxmcp-plus.md).

---

## A stray custom header silently overrides your auth key

**Symptom**: a tool server connection's Bearer key field shows the correct
value, but requests still fail with an authentication error — and this
persists even after re-typing the key, in a private/incognito browser
window, ruling out browser autofill.

**Cause**: Open WebUI's tool-server connection editor has an "Advanced"
section with a free-form custom-headers field, separate from the main
Bearer-auth field. If an `Authorization` header was ever set there (e.g.
from an earlier experiment), it silently takes precedence over the
top-level Bearer key at request time — the UI gives no indication the two
are in conflict.

**Fix**: expand "Advanced" on the connection and check for a leftover
custom `Authorization` header; remove it and rely solely on the top-level
Bearer field.

**How to confirm this is your problem, if you're stuck**: stand up a
throwaway HTTP listener that just logs whatever headers it receives, point
the connection's URL at it temporarily, and trigger a request — comparing
what actually arrives against what you typed will settle it immediately.
