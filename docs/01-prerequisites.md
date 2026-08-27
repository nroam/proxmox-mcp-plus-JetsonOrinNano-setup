# Prerequisites

## Hardware

- An NVIDIA Jetson device with JetPack installed and GPU-accelerated Docker
  working (`docker info` should show `Default Runtime: nvidia`). This guide
  was built and tested on a Jetson Orin Nano (8GB), which is genuinely tight
  on RAM for this workload — see
  [troubleshooting](06-troubleshooting.md#memory-pressure) if you're on the
  same or smaller.
- A Proxmox VE cluster (or single node) reachable on your network from the
  Jetson.

## Software already working, before you start this guide

- **Docker** with GPU passthrough working. If `docker run --rm --gpus all
  nvidia/cuda:12.2.2-base-ubuntu22.04 nvidia-smi` (or equivalent for your
  JetPack/CUDA version) doesn't show your GPU, fix that first — this guide
  assumes it already works.
- **Ollama**, installed and confirmed to use the GPU for inference. Check with
  `ollama ps` while a model is loaded — it should show a `PROCESSOR` column
  with GPU percentage, not 100% CPU. Getting Ollama GPU-accelerated on Jetson
  is its own rabbit hole depending on your JetPack version; it's out of scope
  for this guide, but worth confirming before proceeding, since a CPU-only
  fallback will make everything downstream painfully slow.

## Network

- The Jetson needs outbound access to your Proxmox API port (default `8006`).
- You'll access the chat UI from another machine on your network, so the
  Jetson's Docker containers need to bind to `0.0.0.0` / host networking
  rather than `127.0.0.1` — this guide's commands already do that.

## Proxmox VE

- Admin access to create a scoped API token (see next doc). You do **not**
  need to use a root token — a purpose-built token with minimal privileges is
  both safer and, per the troubleshooting notes, actually helps the small LLM
  behave better (fewer tools it can misuse means fewer places for it to get
  confused).
