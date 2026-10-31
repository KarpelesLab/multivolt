"""Tiny circuit-description layer that emits KiCad schematics and drives PCB generation.

A design is a list of parts; each part maps pin numbers/names to net names.
The same description feeds:
  * write_schematic()  -> .kicad_sch (labels on every pin, grouped by function)
  * pcbgen.build()     -> .kicad_pcb (run under KiCad's bundled Python)
Python 3.9 compatible (KiCad's interpreter).
"""
import datetime
import json
import os
import uuid

import sexp
import symlib
from sexp import Sym, q, fmt

GRID = 2.54
NS = uuid.UUID("6f1c3c1e-2c4e-4d55-9a37-9f6d6b0b7a11")


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


def snap(v, g=GRID):
    return round(v / g) * g


class Part(object):
    def __init__(self, ref, lib_id, value, footprint=None, pins=None, lcsc=None, mpn=None,
                 pcb=None, group=None, dnp=False, in_bom=True, fields=None, desc=None):
        self.ref, self.lib_id, self.value = ref, lib_id, value
        self.sym = symlib.Symbol(lib_id)
        self.footprint = footprint or self.sym.prop("Footprint")
        assert self.footprint, "%s needs a footprint" % ref
        self.lcsc, self.mpn, self.dnp, self.in_bom = lcsc, mpn, dnp, in_bom
        self.pcb = pcb or {}            # dict(x=, y=, rot=, side='F')
        self.group = group or "Misc"
        self.fields = fields or {}
        self.desc = desc
        # resolve pin map -> {pin_number: net or None}
        self.nets = {}
        for key, net in (pins or {}).items():
            for p in self.sym.resolve(str(key)):
                self.nets[p.number] = net
        missing = sorted(set(p.number for p in self.sym.pins) - set(self.nets))
        if missing:
            raise ValueError("%s (%s): unassigned pins %s" % (ref, lib_id, [
                (n, [p.name for p in self.sym.pins if p.number == n][0]) for n in missing]))


class Design(object):
    def __init__(self, name, title, rev="1.0", company="", comments=()):
        self.name, self.title, self.rev, self.company = name, title, rev, company
        self.comments = list(comments)
        self.parts = []
        self.power_flags = []          # nets that need a PWR_FLAG
        self.notes = []                # (group, text) free text on schematic
        self.groups = []               # ordered group names
        self.netclasses = {}           # name -> dict(track=, clearance=, via=, drill=, nets=[...])
        self.root_uuid = uid(name, "root")

    # ------------------------------------------------------------------ build
    def add(self, *a, **k):
        p = Part(*a, **k)
        if any(x.ref == p.ref for x in self.parts):
            raise ValueError("duplicate ref " + p.ref)
        self.parts.append(p)
        if p.group not in self.groups:
            self.groups.append(p.group)
        return p

    def note(self, group, text):
        self.notes.append((group, text))
        if group not in self.groups:
            self.groups.append(group)

    def nets(self):
        out = {}
        for p in self.parts:
            for num, net in p.nets.items():
                if net:
                    out.setdefault(net, []).append((p.ref, num))
        return out

    def check(self):
        problems = []
        for net, conns in sorted(self.nets().items()):
            if len(conns) < 2:
                problems.append("net %s has a single connection %s" % (net, conns))
        return problems

    # ------------------------------------------------------------- schematic
    def write_schematic(self, path, paper=None):
        lib_nodes = {}
        items = []          # serialized top-level items (strings)
        sym_uuid = {}

        def label(net, x, y, outward):
            ang, just = {(-1, 0): (180, "right"), (1, 0): (0, "left"),
                         (0, 1): (270, "right"), (0, -1): (90, "left")}[outward]
            items.append('(label %s (at %s %s %d) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) '
                         '(justify %s bottom)) (uuid %s))' % (q(net), fmt(x), fmt(y), ang, just,
                                                               q(uid(self.name, "lbl", net, x, y))))

        def wire(x1, y1, x2, y2):
            items.append('(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid %s))' % (
                fmt(x1), fmt(y1), fmt(x2), fmt(y2), q(uid(self.name, "w", x1, y1, x2, y2))))

        def outward_of(pin):
            return {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[pin.angle % 360]

        def place_symbol(sym, lib_id, ref, value, x, y, unit, props, nets, in_bom=True, on_board=True,
                         dnp=False, key=None):
            lib_nodes[lib_id] = sym.cache_node()
            su = uid(self.name, "sym", key or ref, unit)
            sym_uuid[(ref, unit)] = su
            s = ['(symbol (lib_id %s) (at %s %s 0) (unit %d) (exclude_from_sim no) (in_bom %s) (on_board %s) '
                 '(dnp %s) (uuid %s)' % (q(lib_id), fmt(x), fmt(y), unit, "yes" if in_bom else "no",
                                         "yes" if on_board else "no", "yes" if dnp else "no", q(su))]
            # properties: use library positions
            libprops = {pp[1]: pp for pp in sexp.find_all(sym.node, "property")}
            allprops = [("Reference", ref), ("Value", value)] + [(k, v) for k, v in props if k not in ("Reference", "Value")]
            for i, (k, v) in enumerate(allprops):
                lp = libprops.get(k)
                hide = k not in ("Reference", "Value")
                if lp is not None:
                    at = sexp.find(lp, "at")
                    px, py, pa = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0
                    eff = sexp.find(lp, "effects")
                    lib_hidden = eff is not None and (sexp.find(eff, "hide") is not None or Sym("hide") in eff)
                    hide = hide or lib_hidden
                    if k in ("Reference", "Value"):
                        hide = False
                else:
                    px, py, pa = 0, 0, 0
                s.append('(property %s %s (at %s %s %s) (effects (font (size 1.27 1.27))%s))' % (
                    q(k), q(v), fmt(x + px), fmt(y - py), fmt(pa), " (hide yes)" if hide else ""))
            for p in sym.pins_for_unit(unit):
                s.append('(pin %s (uuid %s))' % (q(p.number), q(uid(self.name, "pin", key or ref, unit, p.number))))
            s.append('(instances (project %s (path %s (reference %s) (unit %d))))' % (
                q(self.name), q("/" + self.root_uuid), q(ref), unit))
            items.append(" ".join(s) + ")")
            # connectivity
            for p in sym.pins_for_unit(unit):
                px, py = x + p.x, y - p.y
                net = nets.get(p.number)
                if net is None:
                    items.append('(no_connect (at %s %s) (uuid %s))' % (fmt(px), fmt(py), q(uid(self.name, "nc", ref, p.number))))
                    continue
                ox, oy = outward_of(p)
                ex, ey = px + ox * GRID, py + oy * GRID
                wire(px, py, ex, ey)
                label(net, ex, ey, (ox, oy))

        # ---------- layout: groups packed in a flow
        def est_label_w(net):
            return 2.54 + 1.0 * len(net) + 1.5

        blocks = []   # (group, [(part, unit, w, h, ox, oy)])
        for g in self.groups:
            ents = []
            for p in self.parts:
                if p.group != g:
                    continue
                for unit in sorted(p.sym.units):
                    x0, y0, x1, y1 = p.sym.bbox(unit)
                    pins = p.sym.pins_for_unit(unit)
                    lw = max([est_label_w(p.nets.get(pp.number) or "") for pp in pins if pp.angle == 0] or [0])
                    rw = max([est_label_w(p.nets.get(pp.number) or "") for pp in pins if pp.angle == 180] or [0])
                    bh = max([est_label_w(p.nets.get(pp.number) or "") for pp in pins if pp.angle == 90] or [0])
                    th = max([est_label_w(p.nets.get(pp.number) or "") for pp in pins if pp.angle == 270] or [0])
                    # sheet coords: y inverted
                    left = -x0 + lw + 2
                    right = x1 + rw + 6     # room for ref/value text
                    top = y1 + th + 3
                    bottom = -y0 + bh + 3
                    ents.append((p, unit, left, right, top, bottom))
            blocks.append((g, ents))

        cursor_x, cursor_y, row_h = 20.0, 25.0, 0.0
        page_w_target = 380.0
        placements = []
        notes_by_group = {}
        for g, t in self.notes:
            notes_by_group.setdefault(g, []).append(t)
        for g, ents in blocks:
            # pack group's entities in rows of max width 170mm
            gx, gy = 0.0, 8.0
            grow_h, gw, positions = 0.0, 0.0, []
            maxw = 175.0
            for (p, unit, left, right, top, bottom) in ents:
                w = left + right
                h = top + bottom
                if gx + w > maxw and gx > 0:
                    gx = 0.0
                    gy += grow_h
                    grow_h = 0.0
                positions.append((p, unit, gx + left, gy + top))
                gx += w
                gw = max(gw, gx)
                grow_h = max(grow_h, h)
            gh = gy + grow_h
            nlines = sum(t.count("\n") + 1 for t in notes_by_group.get(g, []))
            gh += nlines * 2.6 + (3 if nlines else 0)
            gw = max(gw, 60.0)
            if cursor_x + gw > page_w_target and cursor_x > 20:
                cursor_x = 20.0
                cursor_y += row_h + 8
                row_h = 0.0
            placements.append((g, cursor_x, cursor_y, gw, gh, positions))
            cursor_x += gw + 10
            row_h = max(row_h, gh)
        total_w = max(px + w for (_, px, _, w, _, _) in placements) + 20
        total_h = max(py + h for (_, _, py, _, h, _) in placements) + 30
        if paper is None:
            for name, (pw, ph) in (("A4", (297, 210)), ("A3", (420, 297)), ("A2", (594, 420)), ("A1", (841, 594)), ("A0", (1189, 841))):
                if total_w <= pw and total_h <= ph:
                    paper = name
                    break
            else:
                paper = "A0"

        for (g, gx, gy, gw, gh, positions) in placements:
            items.append('(text %s (exclude_from_sim no) (at %s %s 0) (effects (font (size 2.2 2.2) (thickness 0.44) (bold yes)) '
                         '(justify left bottom)) (uuid %s))' % (q(g), fmt(snap(gx, 1.27)), fmt(snap(gy + 4, 1.27)), q(uid(self.name, "gt", g))))
            items.append('(rectangle (start %s %s) (end %s %s) (stroke (width 0.15) (type dash)) (fill (type none)) (uuid %s))' % (
                fmt(gx - 4), fmt(gy - 2), fmt(gx + gw + 2), fmt(gy + gh + 2), q(uid(self.name, "gr", g))))
            ymax = gy
            for (p, unit, ox, oy) in positions:
                x, y = snap(gx + ox), snap(gy + oy)
                props = [("Footprint", p.footprint), ("Datasheet", p.sym.prop("Datasheet") or "~")]
                if p.desc:
                    props.append(("Description", p.desc))
                if p.lcsc:
                    props.append(("LCSC", p.lcsc))
                if p.mpn:
                    props.append(("MPN", p.mpn))
                for k, v in p.fields.items():
                    props.append((k, v))
                place_symbol(p.sym, p.lib_id, p.ref, p.value, x, y, unit, props, p.nets,
                             in_bom=p.in_bom, dnp=p.dnp)
            # notes at the bottom of the group
            ny = gy + gh - sum(t.count("\n") + 1 for t in notes_by_group.get(g, [])) * 2.6
            for t in notes_by_group.get(g, []):
                items.append('(text %s (exclude_from_sim no) (at %s %s 0) (effects (font (size 1.5 1.5)) (justify left top)) (uuid %s))' % (
                    q(t), fmt(snap(gx, 1.27)), fmt(snap(ny, 1.27)), q(uid(self.name, "note", g, t[:30]))))
                ny += (t.count("\n") + 1) * 2.6

        # power flags: placed in a strip at the bottom-left
        flag_sym = symlib.Symbol("power:PWR_FLAG")
        fx, fy = 25.0, snap(total_h - 12)
        for i, net in enumerate(self.power_flags):
            ref = "#FLG%02d" % (i + 1)
            x = snap(fx + i * 25)
            place_symbol(flag_sym, "power:PWR_FLAG", ref, "PWR_FLAG", x, fy, 1, [("Footprint", ""), ("Datasheet", "~")],
                         {"1": net}, in_bom=False, on_board=False, key=ref)
        self._sym_uuid = sym_uuid

        tb = ['(title_block (title %s) (date %s) (rev %s) (company %s)' % (
            q(self.title), q(datetime.date.today().isoformat()), q(self.rev), q(self.company))]
        for i, c in enumerate(self.comments[:9]):
            tb.append('(comment %d %s)' % (i + 1, q(c)))
        tb = " ".join(tb) + ")"

        out = ['(kicad_sch (version 20231120) (generator "eeschema") (generator_version "8.0")',
               '(uuid %s)' % q(self.root_uuid), '(paper %s)' % q(paper), tb, '(lib_symbols']
        for lid in sorted(lib_nodes):
            out.append(sexp.dump(lib_nodes[lid], 1))
        out.append(')')
        out.extend(items)
        out.append('(sheet_instances (path "/" (page "1")))')
        out.append(')')
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        return sym_uuid

    def symbol_uuid(self, ref):
        """UUID of unit 1 of a part (used to link PCB footprints)."""
        return uid(self.name, "sym", ref, min(self._part(ref).sym.units))

    def _part(self, ref):
        for p in self.parts:
            if p.ref == ref:
                return p
        raise KeyError(ref)

    # ---------------------------------------------------------------- project
    def write_project(self, path):
        classes = [{
            "name": "Default", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3,
            "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_gap": 0.25, "diff_pair_width": 0.2,
            "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0,
            "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2147483647}]
        patterns = []
        for i, (name, nc) in enumerate(sorted(self.netclasses.items())):
            c = dict(classes[0])
            c.update({"name": name, "track_width": nc.get("track", 0.25), "clearance": nc.get("clearance", 0.2),
                      "via_diameter": nc.get("via", 0.6), "via_drill": nc.get("drill", 0.3), "priority": i})
            classes.append(c)
            for n in nc["nets"]:
                patterns.append({"netclass": name, "pattern": n})
        pro = {
            "board": {"design_settings": {"defaults": {}, "rules": {
                "min_clearance": 0.15, "min_track_width": 0.1, "min_via_diameter": 0.5, "min_through_hole_diameter": 0.3,
                "min_hole_to_hole": 0.25, "min_copper_edge_clearance": 0.3, "min_hole_clearance": 0.25,
                "min_silk_clearance": 0.0, "min_text_height": 0.6, "min_text_thickness": 0.1},
                "rule_severities": {"silk_overlap": "ignore", "silk_over_copper": "warning", "lib_footprint_issues": "ignore",
                                    "lib_footprint_mismatch": "ignore", "silk_edge_clearance": "ignore", "text_height": "warning",
                                    "footprint_symbol_mismatch": "warning"}}},
            "meta": {"filename": os.path.basename(path), "version": 3},
            "net_settings": {"classes": classes, "meta": {"version": 4}, "netclass_assignments": None,
                             "netclass_patterns": patterns},
            "erc": {"rule_severities": {"lib_symbol_issues": "ignore", "lib_symbol_mismatch": "ignore",
                                        "footprint_link_issues": "ignore", "simulation_model_issue": "ignore"}},
            "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
            "sheets": [[self.root_uuid, "Root"]],
            "text_variables": {},
        }
        with open(path, "w") as f:
            json.dump(pro, f, indent=2)
        # custom DRC rules (JLCPCB-friendly)
        with open(path.replace(".kicad_pro", ".kicad_dru"), "w") as f:
            f.write('(version 1)\n'
                    '(rule "one spoke is enough on secondary pours"\n  (constraint min_resolved_spokes 1))\n')

    def dump_json(self, path):
        """Serialize for pcbgen (which runs under a different Python)."""
        data = {"name": self.name, "title": self.title, "rev": self.rev, "root_uuid": self.root_uuid,
                "parts": [], "netclasses": self.netclasses}
        for p in self.parts:
            data["parts"].append({"ref": p.ref, "value": p.value, "footprint": p.footprint, "lcsc": p.lcsc,
                                  "mpn": p.mpn, "nets": p.nets, "pcb": p.pcb, "dnp": p.dnp, "in_bom": p.in_bom,
                                  "sym_uuid": self.symbol_uuid(p.ref), "lib_id": p.lib_id, "desc": p.desc})
        with open(path, "w") as f:
            json.dump(data, f, indent=1)
