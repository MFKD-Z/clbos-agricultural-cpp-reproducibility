#!/usr/bin/env python3
"""Static integrity and public-sanitization checks for CLBOS v2.0.0."""
from __future__ import annotations
import argparse
import csv
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"
LICENSE_MAP = ROOT / "LICENSE_SCOPE_MAP.csv"

TEXT_SUFFIXES = {".md",".txt",".csv",".json",".cff",".py",".cpp",".h",".hpp",".ps1",".gitignore",".yml",".yaml"}
PRIVATE_PATTERNS = [
    re.compile(r"/mnt/[a-z]/", re.I),
    re.compile(r"[A-Za-z]:\\\\"),
    re.compile(r"/home/[A-Za-z0-9_.-]+/"),
    re.compile(r"DESKTOP-[A-Za-z0-9_-]+", re.I),
]
CANDIDATE_PATTERNS = [
    re.compile(r"2\.0\.0-candidate", re.I),
    re.compile("non-public " + "candidate", re.I),
    re.compile("PENDING_NEW_VERSION_" + "DOI", re.I),
]

def sha256(p: Path):
    h=hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b=f.read(1024*1024)
            if not b: break
            h.update(b)
    return h.hexdigest()

def manifest_entries():
    out={}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        h,path=line.split("  ",1)
        out[path]=h
    return out

def scan_text():
    hits=[]
    for p in ROOT.rglob("*"):
        if not p.is_file() or p == MANIFEST or p.resolve() == Path(__file__).resolve():
            continue
        if p.suffix.lower() not in TEXT_SUFFIXES and p.name not in {"VERSION","CMakeLists.txt",".gitignore"}:
            continue
        text=p.read_text(encoding="utf-8",errors="replace")
        for rx in PRIVATE_PATTERNS:
            m=rx.search(text)
            if m:
                hits.append((str(p.relative_to(ROOT)), "private_path", m.group(0)))
                break
        for rx in CANDIDATE_PATTERNS:
            m=rx.search(text)
            if m:
                hits.append((str(p.relative_to(ROOT)), "candidate_marker", m.group(0)))
                break
    return hits

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--run-analysis", action="store_true")
    args=ap.parse_args()

    failures=[]
    entries=manifest_entries()
    actual=[p for p in ROOT.rglob("*") if p.is_file() and p != MANIFEST]
    actual_rel={str(p.relative_to(ROOT)).replace("\\","/") for p in actual}
    if set(entries) != actual_rel:
        failures.append(f"manifest path-set mismatch: listed={len(entries)} actual={len(actual_rel)}")
    for rel,h in entries.items():
        p=ROOT/rel
        if not p.exists():
            failures.append(f"manifest missing file: {rel}")
        elif sha256(p) != h:
            failures.append(f"manifest hash mismatch: {rel}")

    if LICENSE_MAP.exists():
        rows=list(csv.DictReader(LICENSE_MAP.open(encoding="utf-8-sig",newline="")))
        licensed={r["path"] for r in rows}
        all_rel={str(p.relative_to(ROOT)).replace("\\","/") for p in ROOT.rglob("*") if p.is_file()}
        missing=sorted(all_rel-licensed)
        extra=sorted(licensed-all_rel)
        if missing: failures.append("license map missing: " + ", ".join(missing))
        if extra: failures.append("license map stale paths: " + ", ".join(extra))
    else:
        failures.append("LICENSE_SCOPE_MAP.csv missing")

    hits=scan_text()
    for rel,kind,val in hits:
        failures.append(f"{kind}: {rel}: {val}")

    cff=(ROOT/"CITATION.cff").read_text(encoding="utf-8",errors="replace")
    if "version: 2.0.0" not in cff:
        failures.append("CITATION.cff version is not 2.0.0")
    title="Certified Lower-Bound Orientation Search under Cross-Stage Objective Mismatch in Agricultural Coverage Path Planning"
    if title not in cff:
        failures.append("CITATION.cff title does not match the final manuscript")

    if args.run_analysis:
        for script in ["scripts/reproduce_numbers.py","scripts/reproduce_v2_added.py"]:
            cp=subprocess.run([sys.executable,str(ROOT/script)],cwd=ROOT)
            if cp.returncode:
                failures.append(f"analysis script failed: {script}")

    print(f"MANIFEST_ENTRY_COUNT={len(entries)}")
    print(f"LICENSE_MAP_COVERAGE={'PASS' if not any('license map' in x for x in failures) else 'FAIL'}")
    print(f"PUBLIC_PRIVATE_PATH_SCAN={'PASS' if not any('private_path' in x for x in failures) else 'FAIL'}")
    print(f"CANDIDATE_MARKER_SCAN={'PASS' if not any('candidate_marker' in x for x in failures) else 'FAIL'}")
    print(f"CITATION_METADATA={'PASS' if not any('CITATION.cff' in x for x in failures) else 'FAIL'}")
    if failures:
        print("VERIFY_STATUS=FAIL")
        for x in failures:
            print("FAIL=" + x)
        return 1
    print("VERIFY_STATUS=PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
