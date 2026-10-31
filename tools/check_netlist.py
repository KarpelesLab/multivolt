#!/usr/bin/env python3
"""Compare a KiCad-exported netlist (kicadsexpr) against the design JSON."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexp
net = sexp.parse(open(sys.argv[1]).read())
des = json.load(open(sys.argv[2]))
got = {}
for n in sexp.find_all(sexp.find(net, "nets"), "net"):
    name = sexp.find(n, "name")[1].lstrip("/")
    nodes = frozenset((sexp.find(x, "ref")[1], sexp.find(x, "pin")[1]) for x in sexp.find_all(n, "node"))
    got[nodes] = name
want = {}
for p in des["parts"]:
    for pin, nn in p["nets"].items():
        if nn: want.setdefault(nn, set()).add((p["ref"], pin))
bad = 0
gotsets = {k: v for k, v in got.items()}
for nn, nodes in want.items():
    nodes = frozenset(nodes)
    if nodes not in gotsets:
        bad += 1; print("MISMATCH net", nn, sorted(nodes))
    elif gotsets[nodes] != nn:
        print("name differs", nn, gotsets[nodes])
extra = [ (v, sorted(k)) for k, v in got.items() if not any(frozenset(s)==k for s in want.values()) and len(k)>1 and not v.startswith("unconnected")]
for e in extra: bad += 1; print("EXTRA", e)
print("netlist check:", "OK" if not bad else "%d problems" % bad, "(%d nets)" % len(want))
sys.exit(1 if bad else 0)
