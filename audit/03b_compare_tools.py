#!/usr/bin/env python3
"""
03b_compare_tools.py — score ogr2ogr against the same taxonomy and compare.

Occurrence detection is shared with stage 03: the same normalised model, the
same third-party readers, applied to whichever files a converter produced. Only
the disclosure side differs, because the browser tool emits stable message
identifiers while GDAL emits English sentences. The patterns below were written
against GDAL's message vocabulary rather than against the outputs of this
corpus, and messages matching none of them are counted and listed rather than
assigned by hand.

Usage: python3 03b_compare_tools.py
"""

import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location("gt", HERE / "03_ground_truth.py")
gt = importlib.util.module_from_spec(spec)
sys.modules["gt"] = gt
spec.loader.exec_module(gt)

# --------------------------------------------------------------------------
# GDAL message vocabulary, mapped to taxonomy codes.
# --------------------------------------------------------------------------
OGR_PATTERNS = [
    (r"Normalized/laundered field name", ["A1"]),
    (r"has been truncated to \d+ characters", ["A4"]),
    (r"does not natively support DateTime type", ["A5"]),
    (r"create as date field, though DateTime requested", ["A5"]),
    (r"does not seem to natively support Integer64 type", ["A3"]),
    (r"characters couldn't be converted correctly from UTF-8", ["A7"]),
    (r"does not support arbitrary field creation", ["A8"]),
    (r"Layer name '.*' adjusted to", ["D1"]),
    (r"Attempt to write non-point .* to point shapefile", ["B5"]),
    (r"No known way to write feature with geometry", ["B5"]),
]
# A feature that could not be written is a disclosure that something was not
# carried across; which mechanism caused it is stated by the accompanying
# message, so these count for the two mechanisms that stop a feature being
# written at all.
OGR_PATTERNS += [
    (r"No known way to write feature with geometry 'None'", ["B7"]),
    (r"Attempt to write non-\w+ \(\w+\) geometry to", ["B5"]),
    (r"Latitude .* is invalid\. Valid range", ["C1"]),
    (r"Longitude .* has been modified to fit into range", ["C1"]),
    (r"does not already exist in the output dataset", ["D3"]),
    (r"Unable to have more than one OGR entities layer", ["D3"]),
]

# Messages about the run itself rather than about a mechanism.
OGR_ABORTED = r"Terminating translation prematurely"
OGR_IGNORE = [
    OGR_ABORTED,
    r"use -skipfailures to skip errors",
    r"Unable to write feature",
]


def ogr_codes(messages):
    codes, unmatched = set(), []
    for m in messages:
        if any(re.search(p, m) for p in OGR_IGNORE):
            continue
        hit = False
        for pat, cs in OGR_PATTERNS:
            if re.search(pat, m):
                codes.update(cs)
                hit = True
        if not hit:
            unmatched.append(m)
    return codes, unmatched


# --------------------------------------------------------------------------
# mapshaper message vocabulary.
# Continuation lines listing individual renamings belong to the heading above
# them and carry no code of their own; the heading is what discloses the
# mechanism.
# --------------------------------------------------------------------------
MS_PATTERNS = [
    (r"Field names were truncated to fit", ["A1"]),
    (r"Field names collided after", ["A1", "A2"]),
    (r"Field names cleaned for Shapefile DBF compatibility", ["A7"]),
    (r"Truncated \d+ string to fit the \d+-byte limit", ["A4"]),
    (r"Unable to generate \.prj file", ["C1"]),
    (r"non-WGS\d+ GeoJSON output", ["C1"]),
]
MS_CONTINUATION = r"^\S+ -> \S+$"


def ms_codes(entry):
    codes, unmatched = set(), []
    for m in entry.get("messages", []):
        if re.match(MS_CONTINUATION, m):
            continue
        hit = False
        for pat, cs in MS_PATTERNS:
            if re.search(pat, m):
                codes.update(cs)
                hit = True
        if not hit:
            unmatched.append(m)
    return codes, unmatched


def score(reported_path, work_dir, codes_fn):
    rows = json.loads(Path(reported_path).read_text(encoding="utf-8"))
    gt.WORK = Path(work_dir)
    out, unmatched_all = [], []
    for r in rows:
        if r["fixture"] == "F14":
            continue
        # A target the converter does not write is not a disclosure failure.
        if r.get("unsupported"):
            continue
        try:
            src = gt.load_source(r["file"])
            outm = gt.load_output(r["fixture"], r["target"], r["outputs"])
        except Exception as e:
            out.append({"fixture": r["fixture"], "target": r["target"], "error": str(e)})
            continue
        # Every synthetic fixture except the projected shapefile is in
        # geographic coordinates; GDAL is not asked to report a source system,
        # so it must be supplied here for both tools to be judged alike.
        src_crs = r.get("src") or ("EPSG:3857" if r["fixture"] == "F13" else "EPSG:4326")
        obs, inh = gt.detect(src, outm, r["target"], src_crs)
        occurred = sorted(set(obs) | set(inh))
        rep, un = codes_fn(r)
        unmatched_all += un
        # A conversion that stopped part way through did not produce an output a
        # user would keep. Counting the missing remainder as undisclosed loss
        # would score a refusal as though it were silent damage, so these are
        # held apart and reported as their own number.
        aborted = any(re.search(OGR_ABORTED, m) for m in r.get("messages", []))
        out.append({
            "fixture": r["fixture"], "target": r["target"],
            "occurred": occurred, "reported": sorted(rep),
            "silent": sorted(set(occurred) - rep),
            "aborted": aborted, "error": None,
        })
    return out, unmatched_all


def summarise(name, rows, tax):
    fam = {c: tax["codes"][c]["family"] for c in tax["codes"]}
    occ, rep = defaultdict(int), defaultdict(int)
    aborted = sum(1 for r in rows if r.get("aborted"))
    for r in rows:
        if r.get("error") or r.get("aborted"):
            continue
        for c in r["occurred"]:
            occ[fam[c]] += 1
            if c in r["reported"]:
                rep[fam[c]] += 1
    o = sum(occ.values())
    p = sum(rep.values())
    return {"name": name, "occurred": o, "reported": p,
            "silent": o - p, "rate": (o - p) / o if o else 0,
            "by_family": {f: (occ[f], rep[f]) for f in tax["families"]},
            "aborted": aborted,
            "n": sum(1 for r in rows if not r.get("error") and not r.get("aborted"))}


def main():
    tax = json.loads((HERE / "taxonomy.json").read_text(encoding="utf-8"))

    pafta_rows, _ = score(HERE / "work" / "reported.json", HERE / "work",
                          lambda r: gt.reported_codes(r["reported"]))
    ogr_rows, ogr_unmatched = score(HERE / "work_ogr" / "reported.json", HERE / "work_ogr",
                                    lambda r: ogr_codes(r["messages"]))
    ms_rows, ms_unmatched = score(HERE / "work_ms" / "reported.json", HERE / "work_ms",
                                  ms_codes)

    a = summarise("Pafta", pafta_rows, tax)
    b = summarise("ogr2ogr (GDAL)", ogr_rows, tax)
    c = summarise("mapshaper", ms_rows, tax)

    print(f"{'':<16}{'conv':>6}{'refused':>9}{'occurred':>10}{'reported':>10}{'silent':>8}{'rate':>8}")
    print("-" * 68)
    for s in (a, b, c):
        print(f"{s['name']:<16}{s['n']:>6}{s['aborted']:>9}{s['occurred']:>10}"
              f"{s['reported']:>10}{s['silent']:>8}{s['rate']:>7.0%}")

    # Whole-conversion counts. The paper quotes these, so they are printed
    # here rather than derived by hand from the per-mechanism table.
    def whole(rows):
        live = [r for r in rows if not r.get("error") and not r.get("aborted")]
        any_silent = sum(1 for r in live if r["silent"])
        mute = sum(1 for r in live if r["occurred"] and not r["reported"])
        return len(live), any_silent, mute

    print(f"\n{'whole conversions':<30}{'scored':>10}{'any silent':>12}{'reported nothing':>18}")
    print("-" * 70)
    for name, rows in (("Pafta", pafta_rows), ("ogr2ogr (GDAL)", ogr_rows),
                       ("mapshaper", ms_rows)):
        n, sil, mute = whole(rows)
        print(f"{name:<30}{n:>10}{sil:>12}{mute:>18}")

    print(f"\n{'family':<30}{'Pafta':>14}{'ogr2ogr':>14}{'mapshaper':>14}")
    print("-" * 72)
    for f in sorted(tax["families"]):
        oa, ra = a["by_family"][f]
        ob, rb = b["by_family"][f]
        oc, rc = c["by_family"][f]
        print(f"{f + ' ' + tax['families'][f]:<30}{f'{ra}/{oa}':>14}"
              f"{f'{rb}/{ob}':>14}{f'{rc}/{oc}':>14}")

    # per code, side by side
    def per_code(rows):
        o, r = defaultdict(int), defaultdict(int)
        for row in rows:
            if row.get("error") or row.get("aborted"):
                continue
            for c in row["occurred"]:
                o[c] += 1
                if c in row["reported"]:
                    r[c] += 1
        return o, r

    oa, ra = per_code(pafta_rows)
    ob, rb = per_code(ogr_rows)
    oc, rc = per_code(ms_rows)
    codes = sorted(set(oa) | set(ob) | set(oc), key=lambda x: (x[0], int(x[1:])))
    print(f"\n{'code':<6}{'name':<40}{'Pafta':>11}{'ogr2ogr':>11}{'mapshaper':>11}")
    print("-" * 80)
    for cd in codes:
        f1 = f"{ra[cd]}/{oa[cd]}" if oa[cd] else "-"
        f2 = f"{rb[cd]}/{ob[cd]}" if ob[cd] else "-"
        f3 = f"{rc[cd]}/{oc[cd]}" if oc[cd] else "-"
        print(f"{cd:<6}{tax['codes'][cd]['name'][:39]:<40}{f1:>11}{f2:>11}{f3:>11}")

    for label, un in (("GDAL", ogr_unmatched), ("mapshaper", ms_unmatched)):
        if un:
            u = sorted(set(un))
            print(f"\n{label} messages matching no pattern: {len(un)} "
                  f"({len(u)} distinct)")
            for m in u[:8]:
                print(f"  {m[:100]}")

    json.dump({"pafta": pafta_rows, "ogr": ogr_rows, "mapshaper": ms_rows},
              open(HERE / "work" / "comparison.json", "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
