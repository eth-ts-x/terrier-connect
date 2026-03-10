#!/usr/bin/env python3
"""Render connector JSON templates by replacing ${ENV_VAR} placeholders."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def render(text: str) -> str:
    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        value = os.getenv(name)
        if value is None:
            missing.add(name)
            return match.group(0)
        return value

    rendered = PLACEHOLDER_RE.sub(replace, text)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise SystemExit(f"Missing environment variables: {missing_list}")
    return rendered


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: render_connector.py <input-json> <output-json>", file=sys.stderr)
        return 1

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    rendered = render(input_path.read_text())
    output_path.write_text(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
