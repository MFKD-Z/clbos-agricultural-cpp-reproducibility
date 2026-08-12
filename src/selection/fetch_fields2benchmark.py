#!/usr/bin/env python3
"""Fetch Zenodo metadata and the archive containing the Fields2Benchmark WKT pool."""
import argparse, json, shutil, sys, urllib.request, zipfile
from pathlib import Path

API = "https://zenodo.org/api/records/{record}"

def download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "agri-rough-canary/0"})
    with urllib.request.urlopen(request) as response, target.open("wb") as handle:
        shutil.copyfileobj(response, handle)

def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--record", required=True); p.add_argument("--dest", required=True)
    args = p.parse_args(); dest = Path(args.dest); dest.mkdir(parents=True, exist_ok=True)
    metadata_file = dest / "zenodo_record.json"
    if metadata_file.exists(): metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    else:
        with urllib.request.urlopen(API.format(record=args.record)) as response: metadata = json.load(response)
        metadata_file.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    files = metadata.get("files", [])
    candidates = [f for f in files if "wkt" in f.get("key", "").lower()]
    if not candidates:
        candidates = [f for f in files if f.get("key", "").lower().endswith((".zip", ".tar.gz", ".tgz"))]
    if not candidates: raise RuntimeError("Zenodo record has no WKT-containing asset candidate")
    asset = candidates[0]; key = asset["key"]; archive = dest / key
    if not archive.exists(): download(asset["links"]["self"], archive)
    if archive.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive) as zf: zf.extractall(dest)
    wkt_files = list(dest.rglob("*.wkt"))
    if not wkt_files: raise RuntimeError("downloaded public asset contains no .wkt files")
    (dest / "SOURCE_BINDING.json").write_text(json.dumps({"zenodo_record": args.record, "asset_key": key, "wkt_file_count": len(wkt_files)}, indent=2), encoding="utf-8")
    print(f"Zenodo record {args.record}: {len(wkt_files)} WKT files bound from {key}")
if __name__ == "__main__":
    try: main()
    except Exception as exc: print(f"ASSET_FETCH_ERROR: {exc}", file=sys.stderr); raise
