#!/usr/bin/env python3
"""Patch ProxmoxMCP-Plus's tool descriptions to use your real node names
instead of the built-in placeholder examples (pve, pve1, pve2, proxmox-node2).

Small local LLMs tend to copy these placeholder examples literally into tool
calls, causing hostname-lookup failures. This is a mechanical, word-boundary
find-and-replace across the source tree — it does not touch unrelated
strings like 'pveproxy' or 'pvedaemon' (Proxmox service names).

Usage (run from inside your cloned ProxmoxMCP-Plus checkout):

    python3 patch_tool_descriptions.py node1 node2 node3

Pass your real node names in the order you want them substituted for
pve1/pve2/proxmox-node2 respectively (extra placeholder names beyond the
third are rare in the wild but the pattern list below is easy to extend if
your fork of the source has more).

Review `git diff` after running this before you build — it's a mechanical
patch, not a guarantee.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SRC_DIR = Path("src/proxmox_mcp")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(f"Usage: {sys.argv[0]} <node1> [node2] [node3]")

    if not SRC_DIR.is_dir():
        sys.exit(
            f"{SRC_DIR} not found. Run this from the root of your "
            "ProxmoxMCP-Plus checkout."
        )

    names = sys.argv[1:]
    node1 = names[0]
    node2 = names[1] if len(names) > 1 else names[0]
    node3 = names[2] if len(names) > 2 else names[0]

    replacements = [
        (r"\bpve1\b", node1),
        (r"\bpve2\b", node2),
        (r"\bproxmox-node2\b", node3),
        (r"\bpve\b", node1),
    ]

    files = list(SRC_DIR.glob("**/*.py"))
    total_changes = 0
    for path in files:
        content = path.read_text()
        original = content
        for pattern, repl in replacements:
            content = re.sub(pattern, repl, content)
        if content != original:
            changes = sum(
                1
                for _ in re.finditer(
                    "|".join(p for p, _ in replacements), original
                )
            )
            total_changes += changes
            path.write_text(content)
            print(f"{path}: {changes} replacements")

    print(f"\ntotal: {total_changes} replacements across {len(files)} files scanned")
    print("Review with: git diff")


if __name__ == "__main__":
    main()
