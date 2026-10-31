"""Build a .kicad_pcb from a design JSON (run with KiCad's bundled Python).

usage: pcbgen.py <board_dir> [--no-route] [--passes N]
Reads <name>.design.json + <name>.board.json produced by build_sch.py.
"""
import json
import math
import os
import subprocess
import sys

import pcbnew

FPDIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
HERE = os.path.dirname(os.path.abspath(__file__))
JAVA = os.path.join(HERE, "bin", "java")
FREEROUTING = os.path.join(HERE, "bin", "freerouting.jar")
OX, OY = 100.0, 100.0          # page offset of the design origin (mm)


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


LAYERS = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu, "F.SilkS": pcbnew.F_SilkS, "B.SilkS": pcbnew.B_SilkS,
          "F.Fab": pcbnew.F_Fab, "B.Fab": pcbnew.B_Fab, "F.Mask": pcbnew.F_Mask, "B.Mask": pcbnew.B_Mask,
          "Edge.Cuts": pcbnew.Edge_Cuts, "Cmts.User": pcbnew.Cmts_User}


def layer_id(board, name):
    return LAYERS[name]


def add_outline(board, spec):
    ec = pcbnew.Edge_Cuts
    if "outline" in spec:
        pts = spec["outline"]
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            s = pcbnew.PCB_SHAPE(board)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(pt(*a))
            s.SetEnd(pt(*b))
            s.SetLayer(ec)
            s.SetWidth(mm(0.1))
            board.Add(s)
        return
    w = spec["w"]
    x0, x1 = -w / 2.0, w / 2.0
    y0, y1 = spec["y0"], spec["y1"]
    r = spec.get("corner", 0)
    segs = [((x0 + r, y0), (x1 - r, y0)), ((x1, y0 + r), (x1, y1 - r)),
            ((x1 - r, y1), (x0 + r, y1)), ((x0, y1 - r), (x0, y0 + r))]
    for a, b in segs:
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*a))
        s.SetEnd(pt(*b))
        s.SetLayer(ec)
        s.SetWidth(mm(0.1))
        board.Add(s)
    if r:
        for cx, cy, ang in ((x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90)):
            s = pcbnew.PCB_SHAPE(board)
            s.SetShape(pcbnew.SHAPE_T_ARC)
            s.SetCenter(pt(cx, cy))
            a0 = math.radians(ang)
            s.SetStart(pt(cx + r * math.cos(a0), cy + r * math.sin(a0)))
            s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
            s.SetLayer(ec)
            s.SetWidth(mm(0.1))
            board.Add(s)


def board_poly(spec):
    if "outline" in spec:
        return spec["outline"]
    w = spec["w"]
    return [(-w / 2, spec["y0"]), (w / 2, spec["y0"]), (w / 2, spec["y1"]), (-w / 2, spec["y1"])]


def add_zone(board, nets, z, spec):
    poly = z.get("poly") or board_poly(spec)
    for lname in z["layers"]:
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer_id(board, lname))
        zone.SetNet(nets[z["net"]])
        ol = zone.Outline()
        ol.NewOutline()
        for (x, y) in poly:
            ol.Append(mm(OX + x), mm(OY + y))
        zone.SetAssignedPriority(z.get("priority", 0))
        zone.SetLocalClearance(mm(z.get("clearance", 0.25)))
        zone.SetMinThickness(mm(0.2))
        zone.SetThermalReliefGap(mm(0.3))
        zone.SetThermalReliefSpokeWidth(mm(z.get("spoke", 0.4)))
        if z.get("solid"):
            zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        else:
            zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        board.Add(zone)


def add_text(board, t):
    txt = pcbnew.PCB_TEXT(board)
    txt.SetText(t["text"])
    txt.SetPosition(pt(t["x"], t["y"]))
    lay = t.get("layer", "F.SilkS")
    txt.SetLayer(layer_id(board, lay))
    sz = t.get("size", 1.0)
    txt.SetTextSize(pcbnew.VECTOR2I(mm(sz), mm(sz)))
    txt.SetTextThickness(mm(t.get("thick", max(0.12, sz * 0.15))))
    if t.get("rot"):
        txt.SetTextAngle(pcbnew.EDA_ANGLE(t["rot"], pcbnew.DEGREES_T))
    if lay.startswith("B."):
        txt.SetMirrored(True)
    j = t.get("just", "center")
    txt.SetHorizJustify({"left": pcbnew.GR_TEXT_H_ALIGN_LEFT, "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT,
                         "center": pcbnew.GR_TEXT_H_ALIGN_CENTER}[j])
    board.Add(txt)


def resolve_pt(board, p):
    """[x, y] | "REF.PAD" | ["REF.PAD", dx, dy] -> design coords (x, y)"""
    if isinstance(p, str) or (isinstance(p, list) and isinstance(p[0], str)):
        key, dx, dy = (p, 0.0, 0.0) if isinstance(p, str) else (p[0], p[1], p[2])
        ref, num = key.rsplit(".", 1)
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            raise KeyError("no footprint " + ref)
        for pad in fp.Pads():
            if pad.GetNumber() == num:
                pos = pad.GetPosition()
                return (pcbnew.ToMM(pos.x) - OX + dx, pcbnew.ToMM(pos.y) - OY + dy)
        raise KeyError("no pad %s on %s" % (num, ref))
    return (p[0], p[1])


def add_line(board, ln):
    pts = ln["pts"]
    for a, b in zip(pts[:-1], pts[1:]):
        sh = pcbnew.PCB_SHAPE(board)
        sh.SetShape(pcbnew.SHAPE_T_SEGMENT)
        sh.SetStart(pt(*a))
        sh.SetEnd(pt(*b))
        sh.SetLayer(layer_id(board, ln.get("layer", "F.SilkS")))
        sh.SetWidth(mm(ln.get("width", 0.15)))
        board.Add(sh)


def add_track(board, nets, tr):
    pts = [resolve_pt(board, p) for p in tr["pts"]]
    lay = layer_id(board, tr.get("layer", "F.Cu"))
    for a, b in zip(pts[:-1], pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pt(*a))
        t.SetEnd(pt(*b))
        t.SetWidth(mm(tr.get("width", 0.25)))
        t.SetLayer(lay)
        t.SetNet(nets[tr["net"]])
        t.SetLocked(True)
        board.Add(t)


def add_via(board, nets, v):
    via = pcbnew.PCB_VIA(board)
    x, y = resolve_pt(board, v["at"]) if "at" in v else (v["x"], v["y"])
    via.SetPosition(pt(x, y))
    via.SetWidth(mm(v.get("size", 0.6)))
    via.SetDrill(mm(v.get("drill", 0.3)))
    via.SetNet(nets[v["net"]])
    via.SetLocked(True)
    board.Add(via)


def apply_netclasses(board, des):
    ns = board.GetDesignSettings().m_NetSettings
    dflt = ns.GetDefaultNetclass()
    dflt.SetTrackWidth(mm(0.2))
    dflt.SetClearance(mm(0.15))
    dflt.SetViaDiameter(mm(0.6))
    dflt.SetViaDrill(mm(0.3))
    ns.ClearNetclassPatternAssignments()
    for i, (name, nc) in enumerate(sorted(des.get("netclasses", {}).items())):
        c = pcbnew.NETCLASS(name)
        c.SetTrackWidth(mm(nc.get("track", 0.25)))
        c.SetClearance(mm(nc.get("clearance", 0.2)))
        c.SetViaDiameter(mm(nc.get("via", 0.6)))
        c.SetViaDrill(mm(nc.get("drill", 0.3)))
        c.SetPriority(i)
        ns.SetNetclass(name, c)
        for n in nc["nets"]:
            ns.SetNetclassPatternAssignment(n, name)
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(0.1)
    ds.m_MinClearance = mm(0.15)
    ds.m_CopperEdgeClearance = mm(0.3)
    ds.m_HoleClearance = mm(0.25)
    ns.ClearAllCaches()
    ns.RecomputeEffectiveNetclasses()
    board.SynchronizeNetsAndNetClasses(True)


def fix_project(pcb_path):
    """pcbnew.SaveBoard rewrites the .kicad_pro with defaults: restore our rules."""
    pro = pcb_path.replace(".kicad_pcb", ".kicad_pro")
    d = json.load(open(pro))
    rules = d.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {})
    rules.update({"min_clearance": 0.15, "min_track_width": 0.1, "min_via_diameter": 0.5,
                  "min_through_hole_diameter": 0.3, "min_hole_to_hole": 0.25, "min_copper_edge_clearance": 0.3,
                  "min_hole_clearance": 0.25, "min_silk_clearance": 0.0, "min_text_height": 0.5,
                  "min_text_thickness": 0.1})
    sev = d["board"]["design_settings"].setdefault("rule_severities", {})
    sev.update({"silk_overlap": "ignore", "silk_over_copper": "warning", "lib_footprint_issues": "ignore",
                "lib_footprint_mismatch": "ignore", "silk_edge_clearance": "ignore", "text_height": "warning",
                "footprint_symbol_mismatch": "warning"})
    json.dump(d, open(pro, "w"), indent=2)


def drc_counts(pcb_path):
    fix_project(pcb_path)
    rpt = pcb_path + ".drc.tmp"
    subprocess.run([os.path.join(HERE, "kcli"), "pcb", "drc", "--severity-error", "-o", rpt, pcb_path],
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    txt = open(rpt).read()
    os.remove(rpt)
    import re
    v = int(re.search(r"Found (\d+) DRC violations", txt).group(1))
    u = int(re.search(r"Found (\d+) unconnected pads", txt).group(1))
    return v, u


def build(bdir, route=True, passes=30, tries=8):
    name = os.path.basename(os.path.normpath(bdir))
    des = json.load(open(os.path.join(bdir, name + ".design.json")))
    spec = json.load(open(os.path.join(bdir, name + ".board.json")))
    pcb_path = os.path.join(bdir, name + ".kicad_pcb")

    board = pcbnew.CreateEmptyBoard()
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.m_CopperEdgeClearance = mm(0.3)

    # nets
    nets = {}
    allnets = sorted(set(n for p in des["parts"] for n in p["nets"].values() if n))
    for n in allnets:
        ni = pcbnew.NETINFO_ITEM(board, n)
        board.Add(ni)
        nets[n] = ni

    for p in des["parts"]:
        lib, fpname = p["footprint"].split(":")
        fp = pcbnew.FootprintLoad(os.path.join(FPDIR, lib + ".pretty"), fpname)
        if fp is None:
            raise RuntimeError("footprint not found: " + p["footprint"])
        fp.SetReference(p["ref"])
        fp.SetValue(p["value"])
        fp.SetFPIDAsString(p["footprint"])
        pc = p["pcb"]
        fp.SetPosition(pt(pc.get("x", 0), pc.get("y", 0)))
        fp.SetOrientationDegrees(pc.get("rot", 0))
        board.Add(fp)
        if pc.get("side", "F") == "B":
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetPath(pcbnew.KIID_PATH("/" + p["sym_uuid"]))
        fp.SetSheetname("Root")
        fp.SetSheetfile(name + ".kicad_sch")
        if p.get("lcsc"):
            fp.SetField("LCSC", p["lcsc"])
            f = fp.GetField("LCSC")
            if f is not None:
                f.SetVisible(False)
                f.SetLayer(pcbnew.F_Fab)
        if p.get("dnp"):
            fp.SetDNP(True)
        if not p.get("in_bom", True):
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM)
        padmap = pc.get("padmap", {})
        for pad in fp.Pads():
            num = pad.GetNumber()
            sym_pin = padmap.get(num, num)
            if sym_pin in p["nets"] and p["nets"][sym_pin]:
                pad.SetNet(nets[p["nets"][sym_pin]])
        # reference text placement
        ref = fp.Reference()
        if not spec.get("silk_refs", True) and not pc.get("silk_ref"):
            ref.SetLayer(pcbnew.F_Fab if pc.get("side", "F") == "F" else pcbnew.B_Fab)
        if "ref_at" in pc:
            ref.SetPosition(pt(*pc["ref_at"]))
            ref.SetTextAngle(pcbnew.EDA_ANGLE(pc.get("ref_rot", 0), pcbnew.DEGREES_T))
        if "ref_size" in pc:
            s = pc["ref_size"]
            ref.SetTextSize(pcbnew.VECTOR2I(mm(s), mm(s)))
            ref.SetTextThickness(mm(max(0.1, s * 0.15)))
        fp.Value().SetVisible(False)

    add_outline(board, spec)
    for t in spec.get("texts", []):
        add_text(board, t)
    for ln in spec.get("lines", []):
        add_line(board, ln)
    for tr in spec.get("tracks", []):
        add_track(board, nets, tr)
    for v in spec.get("vias", []):
        add_via(board, nets, v)
    for z in spec.get("zones", []):
        if not z.get("post"):
            add_zone(board, nets, z, spec)

    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(0.1)
    pre = os.path.join(bdir, name + ".preroute.kicad_pcb")
    pcbnew.SaveBoard(pre, board)

    if not route:
        board = pcbnew.LoadBoard(pre)
        apply_netclasses(board, des)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(pcb_path, board)
        print("saved", pcb_path)
        return

    best = None
    for attempt in range(tries):
        board = pcbnew.LoadBoard(pre)
        apply_netclasses(board, des)
        dsn = os.path.join(bdir, name + ".dsn")
        ses = os.path.join(bdir, name + ".ses")
        if os.path.exists(ses):
            os.remove(ses)
        pcbnew.ExportSpecctraDSN(board, dsn)
        variants = [[], ["-is", "random"], ["-us", "global"], ["-us", "hybrid", "-hr", "1:1"], ["-is", "random"],
                    ["-is", "sequential"], ["-is", "random"], ["-is", "random"]]
        cmd = [JAVA, "-jar", FREEROUTING, "-de", dsn, "-do", ses, "-mp", str(passes + 10 * attempt),
               "--gui.enabled=false"] + variants[attempt % len(variants)]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                           timeout=3600)
        for l in r.stdout.splitlines():
            if "Auto-routing stage completed" in l:
                print("  route:", l.split("final score:")[-1].split(",")[0].strip(), l.split("(")[1].split(")")[0])
        if not os.path.exists(ses):
            print("  freerouting produced no session file")
            continue
        pcbnew.ImportSpecctraSES(board, ses)
        nets = {n: board.FindNet(n) for n in nets}
        for z in spec.get("zones", []):
            if z.get("post"):
                add_zone(board, nets, z, spec)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(pcb_path, board)
        viol, unc = drc_counts(pcb_path)
        print("  attempt %d: %d DRC errors, %d unconnected" % (attempt + 1, viol, unc))
        if best is None or (unc, viol) < best[0]:
            best = ((unc, viol), open(pcb_path).read())
        if unc == 0 and viol == 0:
            break
    with open(pcb_path, "w") as f:
        f.write(best[1])
    fix_project(pcb_path)
    print("saved", pcb_path)


if __name__ == "__main__":
    args = sys.argv[1:]
    passes = 30
    if "--passes" in args:
        i = args.index("--passes")
        passes = int(args[i + 1])
        del args[i:i + 2]
    build(args[0], route="--no-route" not in args, passes=passes)
