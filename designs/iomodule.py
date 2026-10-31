"""MultiVolt LVL4: 4-channel fixed-direction dual-supply level translator module.

Breadboard DIP-20 form factor (0.3" row spacing, straddles the centre channel).
Each channel: SN74LXC1T45 (1.1..5.5 V on both sides, 420 Mbps, no auto direction sensing).
  * Input threshold follows the supply of the input side, output swings to the supply of the output side.
  * DIRn high (or open: 100k pull-up to VA) -> data flows A->B.  DIRn low -> B->A.
  * DIR is referenced to VA.

Left row  (J1, A side):  1 VA, 2 A1, 3 DIR1, 4 A2, 5 DIR2, 6 A3, 7 DIR3, 8 A4, 9 DIR4, 10 GND
Right row (J2, B side):  1 VB, 2 B1, 3 GND,  4 B2, 5 GND,  6 B3, 7 GND,  8 B4, 9 GND,  10 GND
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from kigen import Design  # noqa: E402

P = 2.54
ROW = 3.81          # header rows at x = -/+ 3.81 mm (0.3" apart)


def build():
    d = Design("lvl4", "MultiVolt LVL4 - 4ch level translator", rev="1.0",
               comments=["SN74LXC1T45 x4, fixed direction per channel (DIRn pin)",
                         "VA/VB: 1.1 V .. 5.5 V each, independent",
                         "DIRn high/open = A->B, low = B->A (DIR referenced to VA)"])

    R0402 = "Resistor_SMD:R_0402_1005Metric"
    C0402 = "Capacitor_SMD:C_0402_1005Metric"

    def ypin(i):            # header pin i (1..10) y position
        return (i - 1) * P

    # headers ---------------------------------------------------------------
    j1 = {1: "VA", 10: "GND"}
    j2 = {1: "VB", 10: "GND"}
    for k in range(1, 5):
        j1[2 * k] = "A%d" % k
        j1[2 * k + 1] = "DIR%d" % k
        j2[2 * k] = "B%d" % k
        j2[2 * k + 1] = "GND"
    d.add("J1", "Connector_Generic:Conn_01x10", "A side",
          "Connector_PinHeader_2.54mm:PinHeader_1x10_P2.54mm_Vertical",
          pins={str(k): v for k, v in j1.items()}, group="Breadboard pins",
          pcb=dict(x=-ROW, y=0, rot=0, side="B"), lcsc="C492409", desc="1x10 male header 2.54mm (pins down)")
    d.add("J2", "Connector_Generic:Conn_01x10", "B side",
          "Connector_PinHeader_2.54mm:PinHeader_1x10_P2.54mm_Vertical",
          pins={str(k): v for k, v in j2.items()}, group="Breadboard pins",
          pcb=dict(x=ROW, y=0, rot=0, side="B"), lcsc="C492409", desc="1x10 male header 2.54mm (pins down)")

    # bulk caps -------------------------------------------------------------
    d.add("C1", "Device:C", "1uF", C0402, pins={"1": "VA", "2": "GND"}, lcsc="C52923",
          group="Breadboard pins", pcb=dict(x=-1.45, y=0.0, rot=90))
    d.add("C2", "Device:C", "1uF", C0402, pins={"1": "VB", "2": "GND"}, lcsc="C52923",
          group="Breadboard pins", pcb=dict(x=1.45, y=0.0, rot=90))

    # channels --------------------------------------------------------------
    for k in range(1, 5):
        yc = P * (2 * k - 0.5)       # cell centre, between An and DIRn rows
        g = "Channel %d" % k
        d.add("U%d" % k, "Logic_LevelTranslator:SN74LVC1T45DCK", "SN74LXC1T45DCK",
              "Package_TO_SOT_SMD:SOT-363_SC-70-6",
              pins={"VCCA": "VA", "GND": "GND", "A": "A%d" % k, "B": "B%d" % k,
                    "DIR": "DIR%d" % k, "VCCB": "VB"},
              lcsc="C5217888", mpn="SN74LXC1T45DCKR", group=g,
              pcb=dict(x=0.0, y=yc + 0.8, rot=0))
        d.add("C%d" % (10 + k), "Device:C", "100nF", C0402, pins={"1": "VA", "2": "GND"},
              lcsc="C1525", group=g, pcb=dict(x=-1.45, y=yc - 1.4, rot=90))
        d.add("C%d" % (20 + k), "Device:C", "100nF", C0402, pins={"1": "VB", "2": "GND"},
              lcsc="C1525", group=g, pcb=dict(x=1.45, y=yc - 1.4, rot=90))
        d.add("R%d" % k, "Device:R", "100k", R0402, pins={"1": "VA", "2": "DIR%d" % k},
              lcsc="C25741", group=g, pcb=dict(x=0.0, y=yc - 1.4, rot=90))

    d.note("Breadboard pins",
           "Pin header rows are 0.3\" apart: the module straddles the breadboard centre channel.\n"
           "Right-row GND pins sit between the B signals for a short return path at high speed.")
    d.note("Channel 1",
           "SN74LXC1T45: VCCA/VCCB 1.1..5.5 V, 420 Mbps, Ioff, VCC isolation.\n"
           "DIR is referenced to VA; 100k pull-up makes an open DIR pin = A->B.")
    d.power_flags = ["VA", "VB", "GND"]
    d.netclasses = {"Power": {"track": 0.4, "clearance": 0.2, "nets": ["VA", "VB", "GND"]}}
    texts = []
    lab1 = {1: "VA", 10: "G"}
    lab2 = {1: "VB", 10: "G"}
    for k in range(1, 5):
        lab1[2 * k], lab1[2 * k + 1] = "A%d" % k, "D%d" % k
        lab2[2 * k], lab2[2 * k + 1] = "B%d" % k, "G"
    for i in range(1, 11):
        texts.append(dict(text=lab1[i], x=-5.55, y=ypin(i), size=0.7, thick=0.13))
        texts.append(dict(text=lab2[i], x=5.55, y=ypin(i), size=0.7, thick=0.13))
    texts += [dict(text="LVL4  A→B", x=0, y=-1.95, size=0.8, thick=0.15),
              dict(text="D=H/open: A→B", x=0, y=ypin(10) + 1.3, size=0.55, thick=0.1),
              dict(text="MultiVolt LVL4 r1", x=0, y=ypin(5) + 1.3, size=0.6, layer="B.SilkS"),
              dict(text="1.1-5.5V", x=0, y=ypin(6) + 0.2, size=0.6, layer="B.SilkS")]
    stitch = [dict(net="GND", x=x, y=y) for x in (-5.0, 5.0) for y in (-2.0, ypin(10) + 1.6)]
    d.board = dict(w=12.7, y0=-2.9, y1=ypin(10) + 2.4, corner=1.0, silk_refs=False, texts=texts, vias=stitch,
                   zones=[dict(net="GND", layers=["B.Cu"], priority=0, clearance=0.2, spoke=0.3),
                          dict(net="GND", layers=["F.Cu"], priority=0, clearance=0.2, spoke=0.3, post=True)])
    return d


if __name__ == "__main__":
    d = build()
    for p in d.check():
        print("WARN", p)
