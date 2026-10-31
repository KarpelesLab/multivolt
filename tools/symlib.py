"""Load KiCad symbols (from system libraries or a project library), flatten `extends`, expose pins."""
import copy
import os
import re

import sexp
from sexp import Sym, find, find_all

KICAD_SYM_DIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"
EXTRA_LIBS = {}  # libname -> path (project libraries)

_cache = {}


def _load_lib(lib):
    if lib not in _cache:
        path = EXTRA_LIBS.get(lib) or os.path.join(KICAD_SYM_DIR, lib + ".kicad_sym")
        with open(path, encoding="utf-8") as f:
            tree = sexp.parse(f.read())
        _cache[lib] = {s[1]: s for s in find_all(tree, "symbol")}
    return _cache[lib]


class Pin(object):
    def __init__(self, number, name, etype, x, y, angle, length, unit):
        self.number, self.name, self.etype = number, name, etype
        self.x, self.y, self.angle, self.length, self.unit = x, y, angle, length, unit

    def __repr__(self):
        return "Pin(%s %s u%d)" % (self.number, self.name, self.unit)


class Symbol(object):
    def __init__(self, lib_id):
        self.lib_id = lib_id
        lib, name = lib_id.split(":", 1)
        syms = _load_lib(lib)
        node = copy.deepcopy(syms[name])
        ext = find(node, "extends")
        if ext:
            parent = copy.deepcopy(syms[ext[1]])
            # child properties override parent's
            child_props = {p[1]: p for p in find_all(node, "property")}
            merged = [Sym("symbol"), name]
            for item in parent[2:]:
                if isinstance(item, list) and item[0] == "property" and item[1] in child_props:
                    merged.append(child_props.pop(item[1]))
                elif isinstance(item, list) and item[0] == "symbol":
                    item = copy.deepcopy(item)
                    item[1] = re.sub("^" + re.escape(ext[1]) + "_", name + "_", item[1])
                    merged.append(item)
                else:
                    merged.append(item)
            # insert remaining child props after the last property
            idx = max(i for i, x in enumerate(merged) if isinstance(x, list) and x[0] == "property") + 1
            for p in child_props.values():
                merged.insert(idx, p)
                idx += 1
            node = merged
        self.name = name
        self.node = node
        self.pins = []
        self.units = set()
        for sub in find_all(node, "symbol"):
            m = re.match(r".*_(\d+)_(\d+)$", sub[1])
            unit, style = int(m.group(1)), int(m.group(2))
            if style not in (0, 1):
                continue
            if unit:
                self.units.add(unit)
            for p in find_all(sub, "pin"):
                at = find(p, "at")
                ln = find(p, "length")
                nm = find(p, "name")[1]
                num = find(p, "number")[1]
                self.pins.append(Pin(num, nm, str(p[1]), float(at[1]), float(at[2]),
                                     int(float(at[3])) if len(at) > 3 else 0, float(ln[1]), unit))
        if not self.units:
            self.units = {1}
        self.power = find(node, "power") is not None

    def prop(self, key):
        for p in find_all(self.node, "property"):
            if p[1] == key:
                return p[2]
        return None

    def cache_node(self):
        """Symbol node renamed as `Lib:Name` for the schematic lib_symbols section."""
        n = copy.deepcopy(self.node)
        n[1] = self.lib_id
        return n

    def pins_for_unit(self, unit):
        return [p for p in self.pins if p.unit in (0, unit)]

    def resolve(self, key):
        """Map a pin key (number or unique name) to pin objects (all pins sharing that number)."""
        byn = [p for p in self.pins if p.number == key]
        if byn:
            return byn
        byname = [p for p in self.pins if p.name == key]
        nums = set(p.number for p in byname)
        if len(nums) == 1:
            return byname
        if len(nums) > 1:
            raise KeyError("%s: pin name %r is ambiguous (%s)" % (self.lib_id, key, sorted(nums)))
        raise KeyError("%s: no pin %r. Pins: %s" % (self.lib_id, key,
                                                    sorted(set((p.number, p.name) for p in self.pins))))

    def bbox(self, unit):
        xs, ys = [], []
        for p in self.pins_for_unit(unit):
            xs.append(p.x)
            ys.append(p.y)
        for sub in find_all(self.node, "symbol"):
            m = re.match(r".*_(\d+)_(\d+)$", sub[1])
            if int(m.group(1)) not in (0, unit):
                continue
            for g in sub[2:]:
                if not isinstance(g, list):
                    continue
                for k in ("start", "end", "center"):
                    e = find(g, k)
                    if e:
                        xs.append(float(e[1]))
                        ys.append(float(e[2]))
                pts = find(g, "pts")
                if pts:
                    for xy in find_all(pts, "xy"):
                        xs.append(float(xy[1]))
                        ys.append(float(xy[2]))
        if not xs:
            return (-2.54, -2.54, 2.54, 2.54)
        return (min(xs), min(ys), max(xs), max(ys))
