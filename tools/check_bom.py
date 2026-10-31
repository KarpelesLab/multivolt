#!/usr/bin/env python3
"""Verify every LCSC code of a design against the JLCPCB catalogue and estimate BOM cost.
usage: check_bom.py boards/<name>/<name>.design.json [qty]"""
import json, sys, urllib.request
URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
def lookup(code):
    req = urllib.request.Request(URL, data=json.dumps({"keyword": code, "currentPage": 1, "pageSize": 10}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    for c in json.load(urllib.request.urlopen(req, timeout=30))["data"]["componentPageInfo"]["list"] or []:
        if c["componentCode"] == code:
            return c
des = json.load(open(sys.argv[1])); qty = int(sys.argv[2]) if len(sys.argv) > 2 else 50
need = {}
for p in des["parts"]:
    if p.get("dnp") or not p.get("in_bom", True) or not p.get("lcsc"):
        if p.get("in_bom", True) and not p.get("dnp") and not p.get("lcsc"): print("NO LCSC:", p["ref"])
        continue
    need.setdefault(p["lcsc"], []).append(p)
total, ext, bad = 0.0, 0, 0
for code, ps in sorted(need.items()):
    c = lookup(code)
    n = len(ps) * qty
    if not c:
        print("%-10s NOT FOUND  (%s)" % (code, ",".join(p["ref"] for p in ps))); bad += 1; continue
    price = c["componentPrices"][0]["productPrice"]
    for pr in c["componentPrices"]:
        if pr["startNumber"] <= n: price = pr["productPrice"]
    total += price * len(ps)
    ext += c["componentLibraryType"] != "base"
    flag = "LOW STOCK" if c["stockCount"] < n else ""
    if flag: bad += 1
    print("%-10s %-6s stock=%-8d $%.4f x%-2d %-22s %-14s %-12s %s %s" % (code, c["componentLibraryType"], c["stockCount"], price, len(ps),
          c["componentModelEn"][:22], c.get("componentSpecificationEn", "")[:14], ps[0]["value"][:12], ",".join(p["ref"] for p in ps)[:40], flag))
print("== %s: %d unique parts (%d extended), parts cost per board at qty %d: $%.2f, problems: %d" % (des["name"], len(need), ext, qty, total, bad))
