# Ollama setup

This assumes Ollama is already installed and GPU-accelerated on your Jetson
(see [prerequisites](01-prerequisites.md) — that part is JetPack/CUDA-version
specific and out of scope here).

## Pick a model

**Recommendation: `qwen2.5:7b-instruct-q4_K_M`.** This is the model this
guide's other docs (and the troubleshooting notes) assume.

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
```

Confirm it advertises tool-calling support:

```bash
curl -s http://127.0.0.1:11434/api/show -d '{"model":"qwen2.5:7b-instruct-q4_K_M"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["capabilities"])'
```

You want to see `tools` in the list.

## Why not a newer/bigger model?

Tempting, but two things bit us specifically on Jetson Orin Nano (8GB):

- **Memory.** A model whose actual runtime footprint (weights + KV cache,
  not just the download size) doesn't comfortably fit alongside Open WebUI
  and Docker overhead will cause severe swap-thrashing — symptoms include
  a request that never completes, 90%+ CPU with 0% GPU utilization, and the
  underlying process needing a hard restart to recover. See
  [troubleshooting](06-troubleshooting.md#memory-pressure) for how to
  diagnose this if you see it.
- **Chat template mismatches on newer model families.** We specifically hit
  this with Qwen3 (both 4B and 8B) on Ollama 0.32.14: Ollama substitutes its
  own generic ChatML template for any request that includes tool
  definitions, rather than using the model's own bundled template — and
  that substitute doesn't know about Qwen3's "thinking mode" stop
  conventions. Result: generation that never terminates. See
  [troubleshooting](06-troubleshooting.md#qwen3-runaway-generation) for the
  full diagnosis if you want to verify this against your own Ollama
  version — it may be fixed by the time you read this.

If you have more RAM to spare, or a fixed/newer Ollama, it's worth
re-testing a bigger or newer model against the verification steps in
[troubleshooting](06-troubleshooting.md) — this guide's choice is a
snapshot of what was reliable on specific, constrained hardware, not a
ceiling.

## Sanity check

```bash
ollama run qwen2.5:7b-instruct-q4_K_M "Say hello in one sentence."
```

Should return quickly (a few seconds) and use the GPU — check with
`ollama ps` while it's running; the `PROCESSOR` column should show GPU
usage, not 100% CPU.
