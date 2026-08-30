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
- The MCP and OpenAPI services in this guide bind only to the Jetson's
  loopback interface. Open WebUI runs with host networking and can reach both
  at `127.0.0.1`, so they do not need to be exposed to the rest of the LAN.
- You'll access the chat UI from another machine on your network. Restrict
  TCP port `3000` to a trusted subnet with the Jetson's firewall. Put Open
  WebUI behind HTTPS and an authenticated reverse proxy before allowing access
  from any untrusted network.

## Proxmox VE

- Admin access to create a scoped API token (see next doc). You do **not**
  need to use a root token. A purpose-built, privilege-separated token with
  read-only permissions is both safer and, per the troubleshooting notes,
  helps the small LLM behave better.
