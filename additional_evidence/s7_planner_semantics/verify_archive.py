"""Read-only verification of the public, coordinate-free S7 evidence package."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
COORDINATE_KEYS = {"point", "end", "points", "expected", "observed", "start_expected", "end_expected", "angle", "route_connections"}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rows(name: str):
    with (ROOT / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def jsonl(name: str):
    with (ROOT / name).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def no_coordinates(value) -> bool:
    if isinstance(value, dict):
        return not (set(value) & COORDINATE_KEYS) and all(no_coordinates(item) for item in value.values())
    if isinstance(value, list):
        return all(no_coordinates(item) for item in value)
    return True


def main() -> None:
    manifest = json.loads((ROOT / "publication_manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["publication_sha256"].items():
        path = ROOT / name
        assert path.is_file() and sha(path) == expected, f"publication checksum mismatch: {name}"
    inventory = manifest["source_inventory"]
    source_manifest = json.loads((ROOT / "s7_evidence_manifest.json").read_text(encoding="utf-8"))
    for name, expected in source_manifest["file_sha256"].items():
        assert inventory[name]["sha256"] == expected, f"original S7 checksum mismatch: {name}"
    closure_manifest = json.loads((ROOT / "s7_polyline_closure/s7_polyline_evidence_manifest.json").read_text(encoding="utf-8"))
    for name, expected in closure_manifest["output_sha256"].items():
        assert inventory["s7_polyline_closure/" + name]["sha256"] == expected, f"original closure checksum mismatch: {name}"

    plan = json.loads((ROOT / "s7_predeclared_cases.json").read_text(encoding="utf-8"))
    results = rows("s7_case_results.csv")
    observations = jsonl("s7_observations.jsonl")
    audits = jsonl("s7_case_audits.jsonl")
    failures = jsonl("s7_failures.jsonl")
    poly = rows("s7_polyline_closure/s7_polyline_case_checks.csv")
    key = lambda item: (item["field_id"], str(item["angle_deg"]))
    assert len(plan) == len(results) == 133
    assert len({key(item) for item in plan}) == 133
    assert {key(item) for item in plan} == {key(item) for item in results}
    statuses = Counter(item["run_status"] for item in results)
    assert statuses == {"SUCCESS": 6, "UNRESOLVED_NOT_RUN_AFTER_A3_FAILURE": 127}, statuses
    assert len(observations) == len(audits) == 6
    assert {key(item) for item in observations} == {key(item) for item in audits}
    strict = Counter(item["A3_status"] for item in results if item["run_status"] == "SUCCESS")
    assert strict == {"FAIL": 3, "PASS": 3}, strict
    assert sum(int(item["gap_count_1e_6"]) for item in results if item["run_status"] == "SUCCESS") == 48085
    failure_statuses = Counter(item.get("A3_status", item.get("status")) for item in failures)
    assert failure_statuses == {"FAIL": 3, "UNRESOLVED_NOT_RUN_AFTER_A3_FAILURE": 127}, failure_statuses
    connectors = [item for item in poly if item["row_type"] == "CONNECTOR"]
    cases = [item for item in poly if item["row_type"] == "CASE"]
    assert len(connectors) == 44 and len(cases) == 6
    assert all(item["polyline_status"] == "PASS" for item in connectors)
    assert sum(int(item["nonwork_state_count"]) for item in connectors) == 57132
    assert sum(state["type"] == 2 for item in observations for state in item["observation"]["states"]) == 57132
    assert all(no_coordinates(item) for item in observations + audits + failures + plan)
    print("PUBLIC_HASHES=PASS")
    print("ORIGINAL_HASH_REFERENCES=PASS")
    print("PLANNED_EXECUTED_UNEXECUTED=133/6/127")
    print("STRICT_A3=FAIL; FAILING_CASES=3/6; GAPS_1E6=48085")
    print("SAMPLED_POLYLINE=44/44_PASS; NONWORK_STATES=57132")
    print("COORDINATE_REDACTION=PASS; GEOMETRIC_REANALYSIS=RESTRICTED_LOCAL_TRACE")


if __name__ == "__main__":
    main()
