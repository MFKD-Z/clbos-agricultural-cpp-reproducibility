"""Make coordinate-free publication copies of the existing S7 audit.

This script never executes a planner or writes to the original audit tree.
It is a publication transform, not part of the original 2026-10-11 run.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


REQUIRED = (
    "S7_PINNED_PLANNER_AUDIT.md",
    "s7_predeclared_cases.json",
    "s7_observations.jsonl",
    "s7_failures.jsonl",
    "s7_case_audits.jsonl",
    "s7_case_results.csv",
    "s7_polyline_closure/S7_POLYLINE_IMPLEMENTATION_CLOSURE.md",
    "s7_polyline_closure/s7_source_callchain.csv",
    "s7_polyline_closure/s7_branch_coverage.csv",
    "s7_polyline_closure/s7_proof_obligation_matrix.csv",
)
PUBLIC = REQUIRED + (
    "s7_evidence_manifest.json",
    "s7_polyline_closure/s7_polyline_evidence_manifest.json",
    "s7_observer.cpp",
    "s7_audit.py",
    "finalize.py",
    "negative_selftest.json",
    "s7_preflight_blocked_wkt.jsonl",
    "s7_polyline_closure/build_closure.py",
    "s7_polyline_closure/s7_polyline_case_checks.csv",
    "s7_polyline_closure/s7_unresolved_obligations.md",
)
PATH_FIELDS = {"wkt_path", "source_wkt_path", "observation_file", "observation_source"}
COORDINATE_FIELDS = {"point", "end", "points", "expected", "observed", "start_expected", "end_expected", "angle"}
PREFIXES = (
    (re.compile(r"/mnt/[a-z]/[^/]+", re.I), "<ORIGINAL_WORKSPACE>"),
    (re.compile(r"/home/[^/]+/\.cache/[^/]+"), "<ORIGINAL_CACHE>"),
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clean_string(value: str) -> str:
    for pattern, replacement in PREFIXES:
        value = pattern.sub(replacement, value)
    return value


def clean_json(value):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in COORDINATE_FIELDS:
                continue
            if key == "route_connections":
                out["route_connection_point_counts"] = [len(connection) for connection in item]
                continue
            if key in PATH_FIELDS:
                out[key] = "[REDACTED_LOCAL_PATH]"
                continue
            out[clean_string(key)] = clean_json(item)
        return out
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    if isinstance(value, str):
        return clean_string(value)
    return value


def copy_public(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower()
    if suffix == ".json":
        data = clean_json(json.loads(src.read_text(encoding="utf-8")))
        dst.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    elif suffix == ".jsonl":
        with src.open(encoding="utf-8") as inp, dst.open("w", encoding="utf-8", newline="\n") as out:
            for line in inp:
                if line.strip():
                    out.write(json.dumps(clean_json(json.loads(line)), ensure_ascii=False, separators=(",", ":")) + "\n")
    elif suffix == ".csv":
        with src.open(encoding="utf-8", newline="") as inp, dst.open("w", encoding="utf-8", newline="") as out:
            reader = csv.DictReader(inp)
            writer = csv.DictWriter(out, fieldnames=reader.fieldnames, lineterminator="\n")
            writer.writeheader()
            for row in reader:
                writer.writerow({key: "[REDACTED_LOCAL_PATH]" if key in PATH_FIELDS else clean_string(val)
                                 for key, val in row.items()})
    else:
        dst.write_text(clean_string(src.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")


def check_original_manifests(root: Path) -> None:
    original = json.loads((root / "s7_evidence_manifest.json").read_text(encoding="utf-8"))
    for name, expected in original["file_sha256"].items():
        path = root / name
        if not path.is_file() or sha(path) != expected:
            raise RuntimeError(f"original S7 manifest mismatch: {name}")
    closure = json.loads((root / "s7_polyline_closure/s7_polyline_evidence_manifest.json").read_text(encoding="utf-8"))
    for name, expected in closure["output_sha256"].items():
        path = root / "s7_polyline_closure" / name
        if not path.is_file() or sha(path) != expected:
            raise RuntimeError(f"original polyline manifest mismatch: {name}")
    for original_path, expected in closure["frozen_hashes_before"].items():
        rel = original_path.split("/s7_pinned_planner_semantics_audit/", 1)
        if len(rel) == 2 and (root / rel[1]).is_file() and sha(root / rel[1]) != expected:
            raise RuntimeError(f"frozen source mismatch: {rel[1]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="Original S7 audit directory")
    parser.add_argument("--local-manifest", type=Path, required=True, help="Restricted local inventory outside the public repo")
    args = parser.parse_args()
    root = args.source.resolve(strict=True)
    dest = Path(__file__).resolve().parent
    check_original_manifests(root)
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    if missing:
        raise RuntimeError(f"missing original audit files: {missing}")

    source_inventory = {}
    local_inventory = {}
    for source in sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        rel = source.relative_to(root).as_posix()
        stat = source.stat()
        source_inventory[rel] = {"sha256": sha(source), "size_bytes": stat.st_size,
                                 "mtime_ns": stat.st_mtime_ns, "public_copy": rel if rel in PUBLIC else None}
        local_inventory[rel] = {"absolute_path": str(source), **source_inventory[rel]}

    for rel in PUBLIC:
        if rel not in source_inventory:
            raise RuntimeError(f"source for public copy missing: {rel}")
        copy_public(root / rel, dest / rel)

    publish_hashes = {p.relative_to(dest).as_posix(): sha(p) for p in sorted(dest.rglob("*"))
                      if p.is_file() and p.name != "publication_manifest.json"}
    manifest = {
        "scope": "Coordinate-free publication copy of genuine S7 audit; original full traces remain local",
        "original_audit_files_found": len(REQUIRED),
        "original_s7_manifest_sha256": sha(root / "s7_evidence_manifest.json"),
        "original_polyline_manifest_sha256": sha(root / "s7_polyline_closure/s7_polyline_evidence_manifest.json"),
        "source_inventory": source_inventory,
        "publication_sha256": publish_hashes,
        "redactions": {
            "all_json_coordinate_arrays": ["point", "end", "points", "expected", "observed", "start_expected", "end_expected"],
            "all_json_state_angles": ["angle"],
            "route_connections": "replaced point arrays with per-connection point counts",
            "local_path_fields": sorted(PATH_FIELDS),
            "absolute_source_path_patterns": [pattern.pattern for pattern, _ in PREFIXES],
            "omitted_original_files": sorted(set(source_inventory) - set(PUBLIC)),
        },
    }
    (dest / "publication_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    args.local_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.local_manifest.write_text(json.dumps({"source_root": str(root), "inventory": local_inventory,
                                               "public_root": str(dest), "publication_sha256": publish_hashes},
                                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"original audit files={len(REQUIRED)}; public copies={len(PUBLIC)}; original manifest checks=PASS")


if __name__ == "__main__":
    main()
