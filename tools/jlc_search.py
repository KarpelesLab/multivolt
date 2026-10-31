#!/usr/bin/env python3
"""Query the JLCPCB parts library. Usage: jlc_search.py "keyword" [more keywords...]"""
import json, sys, urllib.request

URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"

def search(kw, n=6):
    req = urllib.request.Request(URL, data=json.dumps({"keyword": kw, "currentPage": 1, "pageSize": n}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    return (d.get("data") or {}).get("componentPageInfo", {}).get("list") or []

for kw in sys.argv[1:]:
    print(f"== {kw}")
    for c in search(kw):
        p = c["componentPrices"][0]["productPrice"] if c.get("componentPrices") else None
        p100 = next((x["productPrice"] for x in c.get("componentPrices", []) if x["startNumber"] <= 100 <= (x["endNumber"] if x["endNumber"] > 0 else 10**9)), p)
        print(f'  {c["componentCode"]:>9} {c["componentLibraryType"]:7} stock={c["stockCount"]:<8} ${p100} {c["componentModelEn"]} | {c.get("componentSpecificationEn","")} | {c.get("describe","")[:90]}')
