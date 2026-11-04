#!/usr/bin/env python3
"""Make JLCPCB BOM + CPL from the design JSON and KiCad's position CSV.
usage: jlc_files.py <name.design.json> <pos.csv> <out_dir> [name.kicad_pcb]
The .kicad_pcb (needs KiCad's pcbnew module) is used to centre parts listed in PAD_CENTER.
"""
import csv, json, os, sys
from collections import OrderedDict

# Rotation corrections between KiCad library orientation and JLC/LCSC part orientation,
# keyed by footprint-name prefix (library part dropped).  Verify in JLC's placement preview.
ROT_FIX = {
    "PinHeader_": 90,
    "SW_Push_1P1T_XKB_TS-1187A": 180,
    "SSOP-10-1EP_": 270,
    "SOT-89-3": 180,
    "SOT-583-8": 270,
    "VSSOP-8_": 270,
    "SOT-363_SC-70-6": 180,
}
# Footprints whose KiCad origin is not the part centre (pin 1 for headers, body outline for USB-C/SOT-89):
# JLC places these on the centre of their pads.
PAD_CENTER = ("PinHeader_", "USB_C_Receptacle_", "SOT-89-3")


def fp_name(p):
    return p["footprint"].split(":")[-1]


def rot_fix(p):
    return next((v for k, v in ROT_FIX.items() if fp_name(p).startswith(k)), 0)


pad_ctr = {}
if len(sys.argv) > 4:
    import pcbnew
    for f in pcbnew.LoadBoard(sys.argv[4]).GetFootprints():
        if f.GetFPIDAsString().split(":")[-1].startswith(PAD_CENTER):
            box = pcbnew.BOX2I()
            for pad in f.Pads():
                box.Merge(pad.GetBoundingBox())
            c = box.GetCenter()
            pad_ctr[f.GetReference()] = (pcbnew.ToMM(c.x), -pcbnew.ToMM(c.y))  # pos file is Y-up

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
        rot = (float(r["Rot"]) + rot_fix(p)) % 360
        x, y = (("%.6f" % v) for v in pad_ctr[ref]) if ref in pad_ctr else (r["PosX"], r["PosY"])
        w.writerow([ref, x + "mm", y + "mm", "Top" if r["Side"].lower().startswith("top") else "Bottom",
                    ("%.0f" % rot)])
print("BOM lines:", len(bom), " placements:", sum(len(v) for v in bom.values()))
