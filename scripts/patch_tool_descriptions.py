#!/usr/bin/env python3
"""Patch selected ProxmoxMCP-Plus tool-schema descriptions with real nodes.

Small local LLMs tend to copy these placeholder examples literally into tool
calls, causing hostname-lookup failures. This script is deliberately limited
to the v0.5.14 files that define user-facing tool schemas. It avoids realm
names such as ``user@pve`` and DNS names such as ``pve.proxmox.com``.

Usage (run from inside your cloned ProxmoxMCP-Plus checkout):

    python3 patch_tool_descriptions.py node1 node2 node3

Pass your real node names in the order you want them substituted for
pve1/pve2/proxmox-node2 respectively.

Review `git diff` after running this before you build — it's a mechanical
patch, not a guarantee.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TARGET_FILES = (
    Path("src/proxmox_mcp/tools/definitions.py"),
    Path("src/proxmox_mcp/services/builtin_tool_plugins.py"),
    Path("src/proxmox_mcp/config/models.py"),
)
NODE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(f"Usage: {sys.argv[0]} <node1> [node2] [node3]")

    names = sys.argv[1:]
    invalid_names = [name for name in names if not NODE_NAME.fullmatch(name)]
    if invalid_names:
        sys.exit(f"Invalid Proxmox node name(s): {', '.join(invalid_names)}")

    missing_files = [str(path) for path in TARGET_FILES if not path.is_file()]
    if missing_files:
        sys.exit(
            "Expected v0.5.14 tool-schema file(s) not found: "
            + ", ".join(missing_files)
            + ". Run this from the root of the tested ProxmoxMCP-Plus checkout."
        )

    node1 = names[0]
    node2 = names[1] if len(names) > 1 else names[0]
    node3 = names[2] if len(names) > 2 else names[0]

    replacements = (
        (r"(?<![@\w.-])pve1(?![\w.-])", node1),
        (r"(?<![@\w.-])pve2(?![\w.-])", node2),
        (r"(?<![@\w.-])proxmox-node2(?![\w.-])", node3),
        (r"(?<![@\w.-])pve(?![\w.-])", node1),
    )

    total_changes = 0
    changed_files = 0
    for path in TARGET_FILES:
        content = path.read_text(encoding="utf-8")
        original = content
        file_changes = 0
        for pattern, replacement in replacements:
            content, changes = re.subn(
                pattern,
                lambda _match, value=replacement: value,
                content,
            )
            file_changes += changes

        if content != original:
            path.write_text(content, encoding="utf-8")
            changed_files += 1
            total_changes += file_changes
            print(f"{path}: {file_changes} replacements")

    print(f"\ntotal: {total_changes} replacements across {changed_files} changed files")
    print("Review with: git diff -- src/proxmox_mcp")


if __name__ == "__main__":
    main()
