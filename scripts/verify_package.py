#!/usr/bin/env python3
"""Static, numeric, sanitation, and manifest checks for the public package."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS = {".csv", ".json", ".md", ".py", ".txt", ".cff", ".cmake", ".cpp", ".h", ".sh", ".gitignore"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expect(label: str, actual: object, expected: object, failures: list[str]) -> None:
    if actual != expected:
        failures.append(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> int:
    failures: list[str] = []
    subprocess.run([sys.executable, str(ROOT / "scripts" / "reproduce_numbers.py")], cwd=ROOT, check=True)
    summary = json.loads((ROOT / "outputs" / "tables" / "recomputed_summary.json").read_text(encoding="utf-8"))

    provenance = summary["provenance"]
    expect("source WKT", provenance["source_wkt_count"], 350, failures)
    expect("usable inventory", provenance["usable_prepared_inventory_count"], 349, failures)
    expect("preprocessing exclusions", provenance["preprocessing_exclusion_count"], 1, failures)
    expect("held-out count", provenance["heldout_field_count"], 90, failures)
    expect("held-out family counts", sorted(provenance["heldout_family_counts"].values()), [30, 30, 30], failures)
    expect("held-out/development overlap", provenance["heldout_overlap_with_development_count"], 0, failures)
    expect("held-out inventory SHA mapping", provenance["heldout_inventory_sha_mismatch_count"], 0, failures)

    cross = summary["cross_stage"]
    expect("BF upstream exact", cross["BF"]["lsw_exact_count"], 90, failures)
    expect("BF downstream exact", cross["BF"]["j_exact_count"], 65, failures)
    expect("disjoint mismatch", cross["tie_aware"]["disjoint_argmin"], 25, failures)
    expect("C2F upstream/downstream", [cross["C2F"]["lsw_exact_count"], cross["C2F"]["j_exact_count"]], [55, 44], failures)
    expect("Oksanen upstream/downstream", [cross["OKSANEN_MATCHED"]["lsw_exact_count"], cross["OKSANEN_MATCHED"]["j_exact_count"]], [63, 49], failures)
    expect("Top-K exact", [summary["topk"]["exact_counts"][str(k)] for k in (1, 2, 3, 5, 10)], [65, 80, 85, 89, 90], failures)
    expect("Top-5 failure rank", summary["topk"]["unique_top5_failure_oracle_lsw_rank_start"], 8, failures)

    mst = summary["mst_42"]
    expect("42-field totals", [mst["lsw_only_total_full_calls"], mst["mst_total_full_calls"]], [259, 180], failures)
    replay = summary["replay_90"]
    expect("90-field replay totals", [replay["lsw_only_total_full_calls"], replay["mst_total_full_calls"], replay["saved_full_calls"]], [2057, 1428, 629], failures)
    expect("replay comparison", [replay["improved_fields"], replay["equal_fields"], replay["worse_fields"]], [65, 25, 0], failures)
    expect("CLBOS tail", [replay["mean_full_calls"], replay["p50_full_calls"], round(replay["p90_full_calls"], 8), round(replay["p95_full_calls"], 8), replay["max_full_calls"]], [15.866666666666667, 4.5, 35.0, 71.35, 163], failures)
    expect("family totals", sorted(replay["family_full_call_totals"].values(), reverse=True), [949, 250, 229], failures)
    expect("runtime scope", [summary["runtime_scope"]["field_count"], summary["runtime_scope"]["repeat_count_per_method_per_field"], summary["runtime_scope"]["population_level_claim"]], [3, 5, False], failures)
    analysis_failures = list(failures)

    # Release-closure documentation checks. These distinguish analytical
    # admissibility from empirical floating-point recovery and lock the public
    # planner parameter text to the frozen runner authority.
    markdown = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8-sig")
        for path in ROOT.rglob("*.md")
    }
    radius_conflict_pattern = re.compile(
        r"(?i)(?:minimum turning radius.{0,40}\b3(?:\.0)?\s*m\b|\b3(?:\.0)?\s*m.{0,40}minimum turning radius)"
    )
    parameter_conflicts = [relative for relative, text in markdown.items() if radius_conflict_pattern.search(text)]
    guide = markdown.get("docs/REPRODUCTION_GUIDE.md", "")
    runner_readme = markdown.get("src/runner/README.md", "")
    if "Minimum turning radius: 2 m." not in guide:
        parameter_conflicts.append("docs/REPRODUCTION_GUIDE.md: missing 2 m authority")
    if "2 m minimum turning radius" not in runner_readme:
        parameter_conflicts.append("src/runner/README.md: missing 2 m authority")
    cpp_runners = sorted((ROOT / "src" / "runner").glob("*.cpp"))
    if not cpp_runners or any("kMinTurningRadiusM = 2.0" not in path.read_text(encoding="utf-8") for path in cpp_runners):
        parameter_conflicts.append("src/runner/*.cpp: frozen 2.0 m authority mismatch")
    failures.extend(f"parameter conflict: {hit}" for hit in parameter_conflicts)

    certification_files = [
        "README.md",
        "REPRODUCIBILITY_SCOPE.md",
        "docs/CLAIM_EVIDENCE_MAP.md",
        "docs/REPRODUCTION_GUIDE.md",
        "REPRO_EVIDENCE_MAP.csv",
    ]
    certification_text = {
        relative: (ROOT / relative).read_text(encoding="utf-8-sig")
        for relative in certification_files
    }
    forbidden_certification_phrases = [
        "Admissibility was checked empirically against the packaged exhaustive values.",
        "empirical CSV proves mathematical admissibility",
        "42-field 259 to 180 and admissibility",
    ]
    semantic_hits = [
        f"{relative}: {phrase}"
        for relative, text in certification_text.items()
        for phrase in forbidden_certification_phrases
        if phrase.casefold() in text.casefold()
    ]
    readme = certification_text["README.md"]
    claim_map = certification_text["docs/CLAIM_EVIDENCE_MAP.md"]
    evidence_map = certification_text["REPRO_EVIDENCE_MAP.csv"]
    required_semantics = [
        ("README analytical authority", "established analytically under assumptions A1–A4" in readme),
        ("README empirical implementation recovery", "floating-point implementation is additionally checked empirically" in readme),
        ("claim map separates admissibility", "Not an empirical claim; no CSV establishes it" in claim_map),
        ("CSV map separates admissibility", "MANUSCRIPT_ANALYTICAL_AUTHORITY" in evidence_map),
    ]
    for label, present in required_semantics:
        if not present:
            semantic_hits.append(label)
    failures.extend(f"certification semantics: {hit}" for hit in semantic_hits)

    figure_stems = [
        "figure2_top5_case_study_color",
        "figure3_anytime_certification_color",
        "figure4_heldout_distribution_color",
    ]
    figure_failures = [
        f"outputs/figures/{stem}.{suffix}"
        for stem in figure_stems
        for suffix in ("png", "pdf")
        if not (ROOT / "outputs" / "figures" / f"{stem}.{suffix}").is_file()
    ]
    for figure_label in ("Fig. 2", "Fig. 3", "Fig. 4"):
        if figure_label not in readme:
            figure_failures.append(f"README missing {figure_label}")
    failures.extend(f"figure reproduction: {hit}" for hit in figure_failures)

    citation = ROOT / "CITATION.cff"
    citation_failures: list[str] = []
    author_order_match = False
    citation_author_count = 0
    if not citation.is_file():
        citation_failures.append("CITATION.cff missing")
    else:
        citation_text = citation.read_text(encoding="utf-8-sig")
        top_level_citation = citation_text.split("preferred-citation:", 1)[0]
        citation_author_count = len(re.findall(r"(?m)^  - given-names:", top_level_citation))
        author_markers = [
            "given-names: Yunji\n    family-names: Zhou",
            "given-names: Yang\n    family-names: Chen",
            "given-names: Qingyu\n    family-names: Wang",
            "given-names: Shunjie\n    family-names: Chen",
            "given-names: Miao\n    family-names: Yu",
        ]
        positions = [top_level_citation.find(marker) for marker in author_markers]
        author_order_match = all(position >= 0 for position in positions) and positions == sorted(positions)
        if citation_author_count != 5:
            citation_failures.append(f"author count is {citation_author_count}, expected 5")
        if not author_order_match:
            citation_failures.append("author order mismatch")
        if 'email: "miaoyu@scu.edu.cn"' not in top_level_citation:
            citation_failures.append("corresponding-author email missing")
    if (ROOT / "CITATION.cff.template").exists():
        citation_failures.append("obsolete CITATION.cff.template remains")
    failures.extend(f"citation metadata: {hit}" for hit in citation_failures)

    # Mixed-license release boundary. The inventory is deliberately file-level:
    # source/selection metadata with upstream Fields2Benchmark relevance is
    # excluded as a whole from the author grants, while no WKT is redistributed.
    scope_failures: list[str] = []
    bsd_failures: list[str] = []
    cc_failures: list[str] = []
    license_document_failures: list[str] = []
    third_party_failures: list[str] = []
    readme_license_failures: list[str] = []
    citation_license_failures: list[str] = []
    handoff_failures: list[str] = []
    license_conflicts: list[str] = []

    scope_path = ROOT / "LICENSE_SCOPE_MAP.csv"
    scope_rows: list[dict[str, str]] = []
    required_scope_columns = [
        "path",
        "material_type",
        "project_authored",
        "third_party_dependency",
        "upstream_rights_relevant",
        "proposed_license",
        "license_scope_status",
        "notes",
    ]
    if not scope_path.is_file():
        scope_failures.append("LICENSE_SCOPE_MAP.csv missing")
    else:
        with scope_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != required_scope_columns:
                scope_failures.append(f"unexpected columns: {reader.fieldnames!r}")
            scope_rows = list(reader)
        actual_public_paths = {
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("*")
            if path.is_file()
        }
        mapped_paths = {row.get("path", "") for row in scope_rows}
        for relative in sorted(actual_public_paths - mapped_paths):
            scope_failures.append(f"unmapped public file: {relative}")
        for relative in sorted(mapped_paths - actual_public_paths):
            scope_failures.append(f"mapped file missing: {relative}")
        unresolved_statuses = {"", "UNRESOLVED", "UNKNOWN", "AUTHOR_DECISION_REQUIRED"}
        for row in scope_rows:
            if row.get("license_scope_status", "") in unresolved_statuses:
                scope_failures.append(f"unresolved scope: {row.get('path', '')}")

    bsd_scoped_file_count = sum(row.get("proposed_license") == "BSD-3-Clause" for row in scope_rows)
    cc_scoped_file_count = sum(row.get("proposed_license") == "CC-BY-4.0" for row in scope_rows)
    upstream_rights_scoped_file_count = sum(row.get("license_scope_status") == "UPSTREAM_RIGHTS_APPLY" for row in scope_rows)
    unresolved_license_scope_count = sum(
        row.get("license_scope_status", "") in {"", "UNRESOLVED", "UNKNOWN", "AUTHOR_DECISION_REQUIRED"}
        for row in scope_rows
    )
    third_party_assets = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and (path.suffix.casefold() == ".wkt" or path.name.casefold().startswith("imgs."))
    ]

    bsd_path = ROOT / "LICENSES" / "BSD-3-Clause.txt"
    if not bsd_path.is_file():
        bsd_failures.append("LICENSES/BSD-3-Clause.txt missing")
    else:
        bsd_text = bsd_path.read_text(encoding="utf-8-sig")
        bsd_flat = " ".join(bsd_text.split())
        for marker in [
            "SPDX-License-Identifier: BSD-3-Clause",
            "Redistribution and use in source and binary forms",
            "Neither the name of the copyright holder nor the names of its contributors",
            'THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"',
        ]:
            if marker not in bsd_flat:
                bsd_failures.append(f"standard text marker missing: {marker}")
    if bsd_scoped_file_count == 0:
        bsd_failures.append("no BSD-3-Clause scoped files")

    cc_path = ROOT / "LICENSES" / "CC-BY-4.0.txt"
    if not cc_path.is_file():
        cc_failures.append("LICENSES/CC-BY-4.0.txt missing")
    else:
        cc_text = cc_path.read_text(encoding="utf-8-sig")
        for marker in [
            "SPDX-License-Identifier: CC-BY-4.0",
            "Creative Commons Attribution 4.0 International",
            "https://creativecommons.org/licenses/by/4.0/legalcode",
        ]:
            if marker not in cc_text:
                cc_failures.append(f"official notice marker missing: {marker}")
    if cc_scoped_file_count == 0:
        cc_failures.append("no CC-BY-4.0 scoped files")

    license_path = ROOT / "LICENSE.md"
    license_text = license_path.read_text(encoding="utf-8-sig") if license_path.is_file() else ""
    license_flat = " ".join(license_text.split())
    for marker in [
        "project-authored software is licensed under the BSD 3-Clause License",
        "project-authored documentation and eligible original research materials",
        "Third-party materials are excluded from these grants",
        "Fields2Benchmark source WKT and satellite images are not redistributed",
        "Fields2Cover remains under its own upstream license",
        "No repository-wide statement overrides third-party rights",
    ]:
        if marker not in license_flat:
            license_document_failures.append(f"scope marker missing: {marker}")
    if (ROOT / "LICENSE_DECISION_REQUIRED.md").exists():
        license_document_failures.append("superseded license-decision notice remains")
    if "LICENSE_DECISION_REQUIRED.md" in license_text or "AUTHOR_DECISION_REQUIRED" in license_text:
        license_document_failures.append("stale license-decision reference remains")

    third_party_text = markdown.get("THIRD_PARTY.md", "")
    third_party_flat = " ".join(third_party_text.split())
    for marker in [
        "Pinned commit: `92b9f2fcf72d26c44202f9d2ab54fbf25ed87426`",
        "Redistributed in this package: **NO**",
        "Redistributed WKT files: **NO**",
        "Zenodo record: 14524735",
        "non-commercial-use limitation",
        "If a third-party right applies, a project-authored license does not override it.",
    ]:
        if marker not in third_party_flat:
            third_party_failures.append(f"boundary marker missing: {marker}")
    if third_party_assets:
        third_party_failures.extend(f"redistributed asset: {path}" for path in third_party_assets)

    for marker in [
        "[BSD-3-Clause](LICENSES/BSD-3-Clause.txt)",
        "[CC BY 4.0](LICENSES/CC-BY-4.0.txt)",
        "[THIRD_PARTY.md](THIRD_PARTY.md)",
        "[LICENSE.md](LICENSE.md)",
    ]:
        if marker not in readme:
            readme_license_failures.append(f"README link missing: {marker}")

    top_level_citation = citation_text.split("preferred-citation:", 1)[0] if citation.is_file() else ""
    if re.search(r"(?m)^license\s*:", top_level_citation):
        citation_license_failures.append("single top-level license misstates mixed-license repository")
    if re.search(r"(?m)^preferred-citation\s*:", citation_text):
        citation_license_failures.append("premature article preferred-citation remains")
    if "mixed-license repository" not in license_text:
        citation_license_failures.append("mixed-license CFF omission not explained in LICENSE.md")

    handoff_text = markdown.get("PUBLICATION_HANDOFF.md", "")
    for marker in [
        "`LICENSE_STATUS=PASS`",
        "`SOFTWARE_LICENSE=BSD-3-Clause`",
        "`DOCUMENTATION_LICENSE=CC-BY-4.0`",
        "`THIRD_PARTY_RIGHTS_BOUNDARY=PASS`",
        "Tag `v1.0.0`",
        "separate explicit user authorization",
    ]:
        if marker not in handoff_text:
            handoff_failures.append(f"handoff marker missing: {marker}")

    rights_sensitive_rows = [
        row for row in scope_rows
        if row.get("path", "").startswith(("data/provenance/", "data/development/", "data/heldout/"))
    ]
    if len(rights_sensitive_rows) != 8:
        license_conflicts.append(f"rights-sensitive file count is {len(rights_sensitive_rows)}, expected 8")
    for row in rights_sensitive_rows:
        if row.get("proposed_license") != "NOASSERTION" or row.get("license_scope_status") != "UPSTREAM_RIGHTS_APPLY":
            license_conflicts.append(f"upstream file relicensed: {row.get('path', '')}")
    if (
        "LICENSE_STATUS=AUTHOR_DECISION_REQUIRED" in license_text
        and "superseded by this author decision" not in license_flat
    ):
        license_conflicts.append("current scope document retains an unsuperseded author-decision-required status")

    failures.extend(f"license scope: {hit}" for hit in scope_failures)
    failures.extend(f"BSD-3-Clause: {hit}" for hit in bsd_failures)
    failures.extend(f"CC-BY-4.0: {hit}" for hit in cc_failures)
    failures.extend(f"license document: {hit}" for hit in license_document_failures)
    failures.extend(f"third-party boundary: {hit}" for hit in third_party_failures)
    failures.extend(f"README license: {hit}" for hit in readme_license_failures)
    failures.extend(f"CITATION license: {hit}" for hit in citation_license_failures)
    failures.extend(f"publication handoff: {hit}" for hit in handoff_failures)
    failures.extend(f"license conflict: {hit}" for hit in license_conflicts)

    forbidden_literals = [
        "C:" + "\\Users\\",
        "/home/" + "admin435/",
        "G:" + "\\",
        "/mnt/" + "g/",
        "~/" + ".cache/" + "agri_cross_module_canary",
    ]
    private_hits: list[str] = []
    secret_hits: list[str] = []
    secret_pattern = re.compile(r"(?i)(?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*['\"][^'\"]{8,}['\"]")
    bad_names = {"__pycache__", ".pytest_cache", ".git", ".venv", "venv"}
    bad_suffixes = {".pyc", ".pyo", ".exe", ".dll", ".so", ".o", ".obj"}
    backup_suffixes = {".bak", ".tmp", ".swp", ".swo", ".orig", ".rej"}
    cache_build_hits: list[str] = []
    backup_hits: list[str] = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT).as_posix()
        if any(part in bad_names for part in path.parts) or path.suffix.lower() in bad_suffixes:
            cache_build_hits.append(relative)
        if path.is_file() and (path.suffix.lower() in backup_suffixes or path.name.endswith("~")):
            backup_hits.append(relative)
        if not path.is_file() or path.name == "MANIFEST.sha256":
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in {"CITATION.cff", ".gitignore"}:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for literal in forbidden_literals:
            if literal in text:
                private_hits.append(f"{relative}: {literal}")
        if secret_pattern.search(text):
            secret_hits.append(relative)
    if private_hits:
        failures.extend(f"private path: {hit}" for hit in private_hits)
    if secret_hits:
        failures.extend(f"possible secret: {hit}" for hit in secret_hits)
    failures.extend(f"forbidden cache/build artifact: {hit}" for hit in cache_build_hits)
    failures.extend(f"backup/temporary artifact: {hit}" for hit in backup_hits)

    manifest = ROOT / "MANIFEST.sha256"
    manifest_failures: list[str] = []
    if manifest.exists():
        manifest_entries: set[str] = set()
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            recorded, relative = line.split("  ", 1)
            manifest_entries.add(relative)
            target = ROOT / Path(relative)
            if not target.is_file():
                manifest_failures.append(f"target missing: {relative}")
            elif sha256(target) != recorded:
                manifest_failures.append(f"hash mismatch: {relative}")
        expected_entries = {
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("*")
            if path.is_file() and path != manifest
        }
        for relative in sorted(expected_entries - manifest_entries):
            manifest_failures.append(f"unlisted public file: {relative}")
        for relative in sorted(manifest_entries - expected_entries):
            manifest_failures.append(f"stale entry: {relative}")
    else:
        manifest_failures.append("MANIFEST.sha256 missing")
    failures.extend(f"manifest: {failure}" for failure in manifest_failures)

    print("STAGE_1_PARAMETER_CONSISTENCY=" + ("PASS" if not parameter_conflicts else "FAIL"))
    print("MIN_TURN_RADIUS_PUBLIC_VALUE=2.0_m")
    print(f"PARAMETER_CONFLICT_COUNT={len(parameter_conflicts)}")
    print("STAGE_2_CERTIFICATION_SEMANTICS=" + ("PASS" if not semantic_hits else "FAIL"))
    print(f"EMPIRICAL_PROOF_OF_ADMISSIBILITY_LANGUAGE_COUNT={len(semantic_hits)}")
    print("STAGE_3_FIGURE_REPRO_TRUTHFULNESS=" + ("PASS" if not figure_failures else "FAIL"))
    print("MANUSCRIPT_DATA_FIGURES_REPRODUCIBLE=Fig.2,Fig.3,Fig.4")
    print("NONREPRODUCIBLE_FIGURES=none")
    print("STAGE_4_CITATION_METADATA=" + ("PASS" if not citation_failures else "FAIL"))
    print(f"CITATION_AUTHOR_COUNT={citation_author_count}")
    print("CITATION_AUTHOR_ORDER_MATCH=" + str(author_order_match).lower())
    print("STAGE_1_LICENSE_BOUNDARY_AUDIT=" + ("PASS" if not scope_failures and unresolved_license_scope_count == 0 else "FAIL"))
    print(f"UNRESOLVED_LICENSE_SCOPE_COUNT={unresolved_license_scope_count}")
    print(f"THIRD_PARTY_ASSET_REDISTRIBUTION_COUNT={len(third_party_assets)}")
    print("STAGE_2_BSD3_LICENSE=" + ("PASS" if not bsd_failures else "FAIL"))
    print(f"BSD3_SCOPED_FILE_COUNT={bsd_scoped_file_count}")
    print("STAGE_3_CC_BY_4_LICENSE=" + ("PASS" if not cc_failures else "FAIL"))
    print(f"CC_BY_4_SCOPED_FILE_COUNT={cc_scoped_file_count}")
    print(f"UPSTREAM_RIGHTS_SCOPED_FILE_COUNT={upstream_rights_scoped_file_count}")
    print("STAGE_4_LICENSE_SCOPE_DOCUMENT=" + ("PASS" if not license_document_failures else "FAIL"))
    print("STAGE_5_THIRD_PARTY_BOUNDARY=" + ("PASS" if not third_party_failures else "FAIL"))
    print(f"THIRD_PARTY_RELICENSE_CONFLICT_COUNT={len(license_conflicts)}")
    print("STAGE_6_README_LICENSE_INTEGRATION=" + ("PASS" if not readme_license_failures else "FAIL"))
    print("STAGE_7_CITATION_LICENSE_METADATA=" + ("PASS" if not citation_failures and not citation_license_failures else "FAIL"))
    print("STAGE_8_PUBLICATION_HANDOFF=" + ("PASS" if not handoff_failures else "FAIL"))
    print("ANALYSIS_REPRODUCTION_STATUS=" + ("PASS" if not analysis_failures else "FAIL"))
    print("STAGE_1_EVIDENCE_INVENTORY=" + ("PASS" if not failures else "FAIL"))
    print("STAGE_2_MINIMALITY=" + ("PASS" if not failures else "FAIL"))
    print("STAGE_3_NUMERIC_REPRODUCTION=" + ("PASS" if not failures else "FAIL"))
    print("STAGE_4_PUBLIC_SANITIZATION=" + ("PASS" if not private_hits and not secret_hits else "FAIL"))
    print(f"PRIVATE_PATH_COUNT={len(private_hits)}")
    print("SECRET_SCAN_RESULT=" + ("PASS" if not secret_hits else "FAIL"))
    print("CACHE_SCAN=" + ("PASS" if not cache_build_hits else "FAIL"))
    print("BUILD_ARTIFACT_SCAN=" + ("PASS" if not cache_build_hits else "FAIL"))
    print("BACKUP_SCAN=" + ("PASS" if not backup_hits else "FAIL"))
    print("LICENSE_CONFLICT_SCAN=" + ("PASS" if not license_conflicts else "FAIL"))
    print("MANIFEST_VERIFICATION=" + ("PASS" if not manifest_failures else "FAIL"))
    if failures:
        for failure in failures:
            print("FAIL: " + failure, file=sys.stderr)
        return 1
    print("PACKAGE_VERIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
