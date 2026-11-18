"""make_formats.py — write FORMATS.md from the audit measurements.

The per-format loss inventory is documentation that must not drift from the
measurement it describes, and it also carries prose that no measurement can
produce. The two are kept apart: formats_prose.md holds the written sections
and marks with {{TABLES}} and {{SUMMARY}} where the measured parts belong.
Everything between those markers is generated from work/ground_truth.json and
taxonomy.json, so a change to a detector or to the taxonomy reaches the
documentation on the next run, and the prose survives it.

    python make_formats.py                      # writes ../docs/FORMATS.md
    python make_formats.py --out X.md
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

TARGET_TITLE = {
    "shp": "Shapefile",
    "dxf": "DXF (AC1009 / R12)",
    "geojson": "GeoJSON",
    "kml": "KML",
    "csv": "CSV",
}
ORDER = ["shp", "dxf", "geojson", "kml", "csv"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=str(HERE / "work"))
    ap.add_argument("--out", default=str(HERE.parent / "docs" / "FORMATS.md"))
    ap.add_argument("--prose", default=str(HERE / "formats_prose.md"))
    a = ap.parse_args()

    tax = json.loads((HERE / "taxonomy.json").read_text(encoding="utf-8"))
    codes = tax["codes"]
    rows = json.loads((Path(a.work) / "ground_truth.json").read_text(encoding="utf-8"))
    rows = rows if isinstance(rows, list) else rows.get("rows", [])

    occ = defaultdict(lambda: defaultdict(int))
    rep = defaultdict(lambda: defaultdict(int))
    convs = defaultdict(int)
    for r in rows:
        t = r.get("target")
        if t not in TARGET_TITLE:
            continue
        convs[t] += 1
        reported = set(r.get("reported") or [])
        for c in set(r.get("occurred") or []):
            occ[t][c] += 1
            if c in reported:
                rep[t][c] += 1

    total_o = sum(sum(v.values()) for v in occ.values())
    total_r = sum(sum(v.values()) for v in rep.values())

    L = []
    L.append(f"Taxonomy version {tax.get('version', '?')}. "
             f"{len(rows)} conversions, {total_o} losses, {total_r} reported. "
             "The tables below are generated; do not edit them by hand.")
    L.append("")
    L.append("**Reported** means the conversion log named the loss while it happened. A")
    L.append("loss that is not reported is not necessarily worse, but the user has no way")
    L.append("to know it occurred.")
    L.append("")

    for t in ORDER:
        if t not in occ and t not in convs:
            continue
        L.append(f"## {TARGET_TITLE[t]}")
        L.append("")
        L.append(f"{convs[t]} conversions in the audit corpus.")
        L.append("")
        if not occ[t]:
            L.append("No loss mechanism was observed writing to this format.")
            L.append("")
            continue
        L.append("| Code | Mechanism | Occurred | Reported |")
        L.append("|---|---|---|---|")
        for c in sorted(occ[t], key=lambda x: (x[0], int(x[1:]))):
            name = codes.get(c, {}).get("name", c)
            mark = "" if rep[t][c] == occ[t][c] else "  ⚠"
            L.append(f"| {c} | {name} | {occ[t][c]} | {rep[t][c]}{mark} |")
        L.append("")
        silent = [c for c in occ[t] if rep[t][c] < occ[t][c]]
        if silent:
            L.append("Not fully reported: " + ", ".join(
                f"{c} ({codes.get(c, {}).get('name', c).lower()})"
                for c in sorted(silent, key=lambda x: (x[0], int(x[1:])))) + ".")
            L.append("")

    # The summary is derived, not written: which mechanisms the tool never
    # reports, and how the silent share falls across the targets.
    never = sorted({c for t in occ for c in occ[t]
                    if sum(rep[x][c] for x in rep) == 0},
                   key=lambda x: (x[0], int(x[1:])))
    any_silent = sum(1 for r in rows
                     if set(r.get("occurred") or []) - set(r.get("reported") or []))
    pct = round(100 * (total_o - total_r) / total_o) if total_o else 0

    S = ["## Summary of what is not reported", ""]
    if never:
        S.append("These mechanisms occur and are never reported, in any conversion:")
        S.append("")
        for c in never:
            n = sum(occ[t][c] for t in occ)
            S.append(f"- **{c}, {codes.get(c, {}).get('name', c).lower()}** "
                     f"\u2014 {n} occurrence{'s' if n != 1 else ''}.")
        S.append("")
    S.append(f"Across the audited corpus, {total_o} losses occurred in {len(rows)} "
             f"conversions and {total_r} were reported, leaving {pct} per cent silent. "
             f"{any_silent} of the {len(rows)} conversions carried at least one silent "
             "loss. By target the silent share runs:")
    S.append("")
    S.append("| Target | Occurred | Reported | Silent |")
    S.append("|---|---|---|---|")
    for t in ORDER:
        if not occ[t]:
            continue
        o = sum(occ[t].values())
        rr = sum(rep[t].values())
        S.append(f"| {TARGET_TITLE[t]} | {o} | {rr} | {round(100 * (o - rr) / o)}% |")
    S.append("")

    prose = Path(a.prose).read_text(encoding="utf-8")
    for marker, block in (("{{TABLES}}", "\n".join(L)), ("{{SUMMARY}}", "\n".join(S))):
        if marker not in prose:
            raise SystemExit(f"{a.prose} is missing the {marker} marker")
        prose = prose.replace(marker, block)

    Path(a.out).write_text(prose, encoding="utf-8")
    print(f"written to {a.out}  ({total_o} losses, {total_r} reported, "
          f"{len(never)} mechanisms never reported)")


if __name__ == "__main__":
    main()
