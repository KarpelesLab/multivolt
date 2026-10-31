#!/usr/bin/env python3
"""Find JLC 0402/0603 1% resistor part codes for given values (prefers basic). Usage: jlc_res.py 0402 5.1k 2k ..."""
import json, sys, urllib.request, re
URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
def q(kw, n=30):
    req = urllib.request.Request(URL, data=json.dumps({"keyword": kw, "currentPage": 1, "pageSize": n}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=30))["data"]["componentPageInfo"]["list"] or []
def norm(s):
    s=s.replace('Ω','')
    m=re.fullmatch(r'(\d+(?:\.\d+)?)([kKmM]?)',s); v=float(m.group(1))*{'':1,'k':1e3,'K':1e3,'M':1e6,'m':1e-3}[m.group(2)]; return v
def find(pkg, val):
    v=norm(val)
    hits=[]
    for c in q(f"{val}Ω {pkg} 1%"):
        d=c.get("describe","")
        m=re.search(r'(\d+(?:\.\d+)?)(m|k|M)?Ω',d)
        if not m or c.get("componentSpecificationEn")!=pkg or '±1%' not in d: continue
        vv=float(m.group(1))*{None:1,'m':1e-3,'k':1e3,'M':1e6}[m.group(2)]
        if abs(vv-v)>1e-6*max(1,v): continue
        hits.append((c["componentLibraryType"]!="base", -c["stockCount"], c["componentCode"], c["componentLibraryType"], c["stockCount"]))
    hits.sort()
    return hits[0] if hits else None
if __name__=="__main__":
    pkg=sys.argv[1]
    for val in sys.argv[2:]:
        h=find(pkg,val); print(val, h[2:] if h else "NOT FOUND")
