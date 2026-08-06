#!/usr/bin/env python3
"""
check_manifest.py — validate the manifest against the taxonomy and report the
scoring denominators the audit will use.

Checks:
  1. Every code referenced in the manifest exists in the taxonomy.
  2. Every conditional code is also listed as expected for the same target.
  3. Every fixture file named in the manifest exists on disk, unless external.
  4. Every taxonomy code is exercised by at least one fixture.

Usage: python3 check_manifest.py [--manifest manifest.json] [--taxonomy taxonomy.json] [--dir fixtures]
"""

import argparse
import json
from collections import Counter
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="manifest.json")
    ap.add_argument("--taxonomy", default="taxonomy.json")
    ap.add_argument("--dir", default="fixtures")
    args = ap.parse_args()

    tax = json.loads(Path(args.taxonomy).read_text(encoding="utf-8"))
    man = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    fdir = Path(args.dir)

    known = set(tax["codes"])
    problems = []
    used = Counter()
    conditional_used = Counter()
    per_role = Counter()
    accuracy_covered = set()
    audit_cells = 0

    for fx in man["fixtures"]:
        fid, role = fx["id"], fx["role"]
        per_role[role] += 1

        # 3. file presence
        if not fx.get("external"):
            if not (fdir / fx["file"]).exists():
                problems.append(f"{fid}: file missing on disk ({fx['file']})")
        else:
            if (fdir / fx["file"]).exists():
                print(f"note  {fid}: external fixture is present")
            else:
                print(f"note  {fid}: external fixture not yet supplied")
            continue

        # accuracy-role fixtures exercise codes as metric measurements rather
        # than as disclosure observations; they count for coverage only
        for c in fx.get("accuracy_codes", []):
            if c not in known:
                problems.append(f"{fid}: unknown accuracy code {c}")
            used[c] += 0
            accuracy_covered.add(c)

        exp = fx.get("expected") or {}
        cond = fx.get("conditional") or {}

        for target, codes in exp.items():
            for c in codes:
                if c not in known:
                    problems.append(f"{fid}/{target}: unknown code {c}")
                used[c] += 1
                if role in ("audit", "control"):
                    audit_cells += 1

        for target, codes in cond.items():
            for c in codes:
                if c not in known:
                    problems.append(f"{fid}/{target}: unknown conditional code {c}")
                if c not in exp.get(target, []):
                    problems.append(
                        f"{fid}/{target}: conditional {c} not listed as expected")
                conditional_used[c] += 1

    unexercised = sorted(known - set(used) - accuracy_covered)
    if unexercised:
        problems.append(f"taxonomy codes never exercised: {unexercised}")

    print("\n--- corpus ---")
    for role, n in sorted(per_role.items()):
        print(f"  {role:9s} {n}")
    print(f"  taxonomy codes: {len(known)}")
    print(f"  expected loss cells (audit + control): {audit_cells}")
    print(f"  of which conditional: {sum(conditional_used.values())}")

    if accuracy_covered:
        print(f"  measured in accuracy stratum only: {sorted(accuracy_covered)}")

    print("\n--- code coverage ---")
    for fam, label in tax["families"].items():
        codes = sorted((c for c in known if tax["codes"][c]["family"] == fam),
                       key=lambda s: int(s[1:]))
        line = ", ".join(f"{c}:{used[c]}" for c in codes)
        print(f"  {fam} {label}\n      {line}")

    print()
    if problems:
        for p in problems:
            print(f"FAIL  {p}")
        print(f"\n{len(problems)} problem(s)")
        return 1
    print("OK  manifest consistent with taxonomy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
