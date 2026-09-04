"""Small atomic JSON persistence helper for local dashboard state."""

import json
import os
import tempfile
from pathlib import Path


def atomic_write_json(path: Path, payload: object) -> None:
    """Replace *path* atomically so an interrupted write cannot corrupt state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=".tmp", dir=str(path.parent), text=True
    )
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
