#!/usr/bin/env python3
"""Make JLCPCB BOM + CPL from the design JSON and KiCad's position CSV.
usage: jlc_files.py <name.design.json> <pos.csv> <out_dir>
"""
import csv, json, os, sys
from collections import OrderedDict

# Footprint rotation corrections between KiCad library orientation and JLC/LCSC part orientation.
# Verify in JLC's placement preview before ordering; adjust here if a part shows up rotated.
# Add entries like {"Package_TO_SOT_SMD:SOT-89-3": 180} once confirmed in the JLC preview.
ROT_FIX = {}

des = json.load(open(sys.argv[1]))
out = sys.argv[3]
os.makedirs(out, exist_ok=True)
parts = {p["ref"]: p for p in des["parts"]}

bom = OrderedDict()
for p in des["parts"]:
    if p.get("dnp") or not p.get("in_bom", True):
        continue
    key = (p["value"], p["footprint"], p.get("lcsc") or "")
    bom.setdefault(key, []).append(p["ref"])
with open(os.path.join(out, des["name"] + "_bom_jlc.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (val, fp, lcsc), refs in bom.items():
        w.writerow([val, ",".join(sorted(refs, key=lambda r: (r.rstrip("0123456789"), int("".join(c for c in r if c.isdigit()) or 0)))),
                    fp.split(":")[1], lcsc])

rows = list(csv.DictReader(open(sys.argv[2])))
with open(os.path.join(out, des["name"] + "_cpl_jlc.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for r in rows:
        ref = r["Ref"]
        p = parts.get(ref)
        if p is None or p.get("dnp") or not p.get("in_bom", True):
            continue
        rot = (float(r["Rot"]) + ROT_FIX.get(p["footprint"], 0)) % 360
        w.writerow([ref, r["PosX"] + "mm", r["PosY"] + "mm", "Top" if r["Side"].lower().startswith("top") else "Bottom",
                    ("%.0f" % rot)])
print("BOM lines:", len(bom), " placements:", sum(len(v) for v in bom.values()))
