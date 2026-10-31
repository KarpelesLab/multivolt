#!/usr/bin/env python3
"""Generate schematic + project for a design module. Usage: build_sch.py designs/iomodule.py"""
import importlib.util, os, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("design", sys.argv[1]); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
d = mod.build()
for p in d.check():
    print("WARN:", p)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "boards", d.name)
os.makedirs(out, exist_ok=True)
d.write_schematic(os.path.join(out, d.name + ".kicad_sch"))
d.write_project(os.path.join(out, d.name + ".kicad_pro"))
d.dump_json(os.path.join(out, d.name + ".design.json"))
import json
json.dump(getattr(d, "board", {}), open(os.path.join(out, d.name + ".board.json"), "w"))
print("wrote", os.path.abspath(out))
