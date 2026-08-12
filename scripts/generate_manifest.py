#!/usr/bin/env python3
"""Generate a stable SHA-256 manifest for every public file except the manifest itself."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    paths = sorted(
        (path for path in ROOT.rglob("*") if path.is_file() and path != MANIFEST),
        key=lambda path: path.relative_to(ROOT).as_posix(),
    )
    lines = [f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}" for path in paths]
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"MANIFEST_FILE_COUNT={len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
