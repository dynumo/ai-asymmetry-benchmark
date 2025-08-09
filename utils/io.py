"""I/O helpers for reading benchmark data files."""

from __future__ import annotations

import json
from typing import Generator, Any


def load_jsonl(path: str) -> Generator[Any, None, None]:
    """Yield JSON objects line by line from a ``.jsonl`` file.

    Lines that are empty or contain only whitespace are skipped.
    """
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)
