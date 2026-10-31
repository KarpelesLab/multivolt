"""MultiVolt PSU: USB-C PD breadboard power supply, two independent jumper-selected rails.

Input : USB-C, CH224A PD sink requests 9 V (falls back to whatever the source gives, 5 V min).
Rails : two TPS62933P bucks (3 A parts), one per breadboard side.
        A 2x6 jumper picks 1.2 / 1.5 / 1.8 / 2.5 / 3.3 / 5.0 V by connecting one tap of a resistor
        string to FB.  No jumper -> FB pulled to 3V3 through 1M -> converter idles, rail ~0 V.
        Two jumpers at once -> the voltage lands between the two choices (never above the higher).
Protect: INA301 (latching comparator) on each rail: overcurrent -> ALERT pulls the buck EN low,
        red LED on.  RESET button re-arms both rails.  Trip = 1 A with ILIM jumper fitted, 2 A without.
        Remote sense: FB string sits after the 50 mOhm shunt, so the shunt drop is regulated out.
LEDs  : PD (yellow) = PD contract OK; per rail OK (yellow-green) = TPS62933 power-good; OC (red) = tripped.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import symlib  # noqa: E402
from kigen import Design  # noqa: E402

symlib.EXTRA_LIBS["multivolt"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib",
                                              "multivolt.kicad_sym")

R0402 = "Resistor_SMD:R_0402_1005Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
LED0603 = "LED_SMD:LED_0603_1608Metric"
HDR = "Connector_PinHeader_2.54mm:"

# feedback string (see tools/fb_string.py): top (OUT) -> bottom (GND)
FB_STRING = [("6.34k", "C5713274"), ("2.43k", "C830241"), ("1.62k", "C138038"), ("2.26k", "C226955"),
             ("1.4k", "C2974008"), ("1.5k", "C25867"), ("2.94k", "C42396634")]
TAPS = ["1.2V", "1.5V", "1.8V", "2.5V", "3.3V", "5.0V"]

BOARD_W = 60.0
BOARD_H = 57.0
SEC_X = 17.0             # section centres at -/+ SEC_X
# Breadboard power rails (MB102-style 830, 55-56 mm wide, everything on the 0.1" grid):
# inner rail hole 0.85" from the centreline, outer rail 0.95".
RAIL_INNER = 21.59
RAIL_OUTER = 24.13
RAIL_ROW_Y = (42.8, 55.5)       # two 2-pin headers per side, 5 holes (12.7 mm) apart along the rail
RAIL_ORDER = "G+"               # left-to-right on BOTH sides: "G+" = GND then +, "+G" = + then GND


def build():
    d = Design("mvpsu", "MultiVolt PSU - USB-C PD breadboard supply", rev="1.0",
               comments=["USB-C PD (CH224A, 9 V request) -> 2x TPS62933P, jumper-selected 1.2/1.5/1.8/2.5/3.3/5.0 V",
                         "INA301 latching overcurrent per rail (1 A, or 2 A with ILIM jumper removed)",
                         "Rail pins: 2x2 pins per side, 5 holes apart; GND, + on both sides"])
    texts, tracks, vias, zones = [], [], [], []

    # ================================================================ input
    g = "USB-C PD input"
    d.add("J1", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C",
          "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
          pins={"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND",
                "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
                "A5": "CC1", "B5": "CC2", "A6": "DP", "B6": "DP", "A7": "DM", "B7": "DM", "A8": None, "B8": None},
          lcsc="C165948", mpn="TYPE-C-31-M-12", group=g, pcb=dict(x=0, y=3.75, rot=180))
    d.add("D1", "Device:D_Zener", "SMAJ15A", "Diode_SMD:D_SMA", pins={"1": "VBUS", "2": "GND"},
          lcsc="C86819", desc="15 V TVS on VBUS", group=g, pcb=dict(x=0, y=11.0, rot=0))
    d.add("U1", "Interface_USB:CH224K", "CH224A", "Package_SO:SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm",
          pins={"VDD": "VBUS", "VBUS": "VBUS", "CFG1": "CFG1", "CFG2": None, "CFG3": None, "DP": "DP",
                "DM": "DM", "CC1": "CC1", "CC2": "CC2", "PG": "PD_LED", "GND": "GND"},
          lcsc="C42459160", mpn="CH224A", group=g, desc="USB PD sink (pin 1 = VHV on CH224A, 32 V tolerant)",
          pcb=dict(x=0, y=16.8, rot=0))
    d.add("C1", "Device:C", "1uF 25V", C0402, pins={"1": "VBUS", "2": "GND"}, lcsc="C52923", group=g,
          pcb=dict(x=-4.6, y=14.6, rot=270))
    d.add("R1", "Device:R", "6.8k", R0402, pins={"1": "CFG1", "2": "GND"}, lcsc="C25917", group=g,
          desc="CFG1: 6.8k = request 9 V", pcb=dict(x=4.9, y=13.9, rot=270))
    d.add("D2", "Device:LED", "PD", LED0603, pins={"K": "PD_LED", "A": "PD_LED_A"}, lcsc="C2287",
          mpn="KT-0603Y", group=g, pcb=dict(x=-3.6, y=39.0, rot=0))
    d.add("R2", "Device:R", "1k", R0402, pins={"1": "+3V3", "2": "PD_LED_A"}, lcsc="C11702", group=g,
          pcb=dict(x=-3.6, y=40.5, rot=0))
    d.note(g, "CH224A: VHV (pin 1) and VBUS (pin 8) tied straight to VBUS, CFG2/CFG3 open.\n"
              "6.8k on CFG1 requests 9 V; a 5 V-only source still works (5 V rail then ~4.8 V).")

    g = "3V3 housekeeping"
    d.add("U2", "Regulator_Linear:HT75xx-1-SOT89", "HT7533-1", pins={"VIN": "VBUS", "VOUT": "+3V3", "GND": "GND"},
          lcsc="C14289", group=g, pcb=dict(x=0.4, y=24.0, rot=0))
    d.add("C2", "Device:C", "1uF 25V", C0402, pins={"1": "VBUS", "2": "GND"}, lcsc="C52923", group=g,
          pcb=dict(x=-4.2, y=23.6, rot=270))
    d.add("C3", "Device:C", "10uF", C0603, pins={"1": "+3V3", "2": "GND"}, lcsc="C19702", group=g,
          pcb=dict(x=4.6, y=24.0, rot=270))
    d.add("Q1", "Transistor_FET:Q_Dual_NMOS_S1G1D2S2G2D1", "2N7002DW", "Package_TO_SOT_SMD:SOT-363_SC-70-6",
          pins={"1": "GND", "2": "PG_L", "6": "OKK_L", "4": "GND", "5": "PG_R", "3": "OKK_R"},
          lcsc="C61840", group=g, desc="OK LED drivers (power-good is active high)", pcb=dict(x=0, y=28.6, rot=0))
    d.add("SW1", "Switch:SW_Push", "RESET", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A",
          pins={"1": "RST", "2": "GND"}, lcsc="C318884", group=g, pcb=dict(x=0, y=33.4, rot=0))
    d.add("R3", "Device:R", "10k", R0402, pins={"1": "+3V3", "2": "RST"}, lcsc="C25744", group=g,
          pcb=dict(x=-1.4, y=36.9, rot=0))
    d.add("C4", "Device:C", "1uF", C0402, pins={"1": "RST", "2": "GND"}, lcsc="C52923", group=g,
          desc="holds RESET low ~10 ms at power-up: clears any power-up alert", pcb=dict(x=1.4, y=36.9, rot=0))
    d.note(g, "INA301 RESET high = latch mode. R3/C4 keep it low for ~10 ms after power-up (transparent),\n"
              "so start-up inrush can't latch a fault. SW1 re-arms both rails.")

    # =========================================================== rail sections
    for side, sx, base in (("L", -SEC_X, 10), ("R", SEC_X, 30)):
        section(d, side, sx, base, texts, tracks, vias)

    # aux output header
    d.add("J2", "Connector_Generic:Conn_01x04", "AUX OUT", HDR + "PinHeader_1x04_P2.54mm_Vertical",
          pins={"1": "OUT_L", "2": "GND", "3": "GND", "4": "OUT_R"}, lcsc="C2691448", group="Outputs",
          desc="rail outputs for wiring off-board (pins up)", pcb=dict(x=-3.81, y=46.0, rot=90))
    d.note("Outputs", "Rail pins: two 2-pin headers per side, 5 holes apart along the rail, for MB102-style\n"
                      "breadboards (inner rail 0.85\" / outer rail 0.95\" from centre). Order GND, + on both sides.")

    # ----------------------------------------------------------- board graphics
    texts += [
        dict(text="MultiVolt PSU", x=0, y=54.6, size=1.3, thick=0.22),
        dict(text="r1.0", x=0, y=56.1, size=0.8),
        dict(text="USB-C PD in (requests 9 V)", x=0, y=38, size=0.9, layer="B.SilkS"),
        dict(text="RESET", x=0, y=30.0, size=0.8),
        dict(text="PD", x=-5.6, y=39.0, size=0.8),
        dict(text="L    AUX    R", x=0, y=44.0, size=0.8),
        dict(text="+  G  G  +", x=0, y=48.1, size=0.8),
        dict(text="MultiVolt PSU r1.0 - 1.2..5V rails, 1A/2A latching OCP", x=0, y=30, size=1.0, layer="B.SilkS"),
        dict(text="Rail pins: GND, + on both sides (left to right)", x=0, y=33, size=0.9, layer="B.SilkS"),
    ]
    # --- hand-routed VBUS distribution
    tracks += [
        # both USB VBUS pad pairs, bridged on the bottom layer just below the connector
        dict(net="VBUS", width=0.5, pts=["J1.A9", [-2.45, 9.2]]),
        dict(net="VBUS", width=0.5, pts=["J1.A4", [2.45, 9.2]]),
        dict(net="VBUS", width=0.8, layer="B.Cu", pts=[[-2.45, 9.2], [2.45, 9.2]]),
        # TVS cathode
        dict(net="VBUS", width=0.8, pts=[[-2.45, 9.2], "D1.1"]),
        # left trunk: up past the connector shield, along the top edge, down to the left input caps
        dict(net="VBUS", width=0.8, pts=[[-2.45, 9.2], [-5.6, 9.2], [-5.6, 1.0], [-SEC_X - 9.2, 1.0],
                                         [-SEC_X - 9.2, 3.74]]),
        # right trunk: below the connector GND/shield pads, to the right input caps
        dict(net="VBUS", width=0.8, pts=[[2.45, 9.2], [5.6, 9.2], [5.6, 3.74], [SEC_X - 9.2, 3.74]]),
        # CH224A: VHV (pin 1) from the TVS, VBUS sense (pin 8) from the right trunk
        dict(net="VBUS", width=0.4, pts=["D1.1", [-2.64, 12.6], "U1.1"]),
        dict(net="VBUS", width=0.4, pts=["C1.1", [-3.9, 14.09], [-3.6, 14.8]]),
        dict(net="VBUS", width=0.4, pts=["U1.8", [3.9, 16.8], [3.9, 9.2]]),
        # 3V3 LDO input
        dict(net="VBUS", width=0.4, pts=["C1.1", [-5.4, 14.09], [-5.4, 22.6], "C2.1", "U2.2"]),
    ]
    vias += [dict(net="VBUS", x=-2.45, y=9.2, size=0.7, drill=0.35), dict(net="VBUS", x=2.45, y=9.2, size=0.7, drill=0.35)]
    zones.append(dict(net="GND", layers=["B.Cu"], priority=0, clearance=0.25, spoke=0.4))
    zones.append(dict(net="GND", layers=["F.Cu"], priority=0, clearance=0.25, spoke=0.4, post=True))

    d.power_flags = ["VBUS", "GND"]
    d.netclasses = {
        "Power": {"track": 0.8, "clearance": 0.15,
                  "nets": ["VBUS", "OUT_L", "OUT_R", "VPRE_L", "VPRE_R", "SW_L", "SW_R"]},
        "Supply": {"track": 0.4, "clearance": 0.15, "nets": ["+3V3", "GND"]},
    }
    h = BOARD_W / 2
    d.board = dict(w=BOARD_W, y0=0.0, y1=BOARD_H, corner=2.0, silk_refs=False, texts=texts,
                   tracks=tracks, vias=vias, zones=zones)
    return d


def section(d, s, sx, base, texts, tracks, vias):
    """One rail: buck + shunt monitor + jumper string.  s = 'L'|'R', sx = section centre x."""
    g = "Rail %s (%s side)" % (s, "left" if s == "L" else "right")
    n = lambda name: "%s_%s" % (name, s)          # noqa: E731
    C = lambda k: "C%d" % (base + k)              # noqa: E731
    R = lambda k: "R%d" % (base + k)              # noqa: E731
    U_BUCK, U_INA, IND = "U%d" % (3 if s == "L" else 4), "U%d" % (5 if s == "L" else 6), "L%d" % (1 if s == "L" else 2)

    sign = -1 if s == "L" else 1
    pin_x = sorted([sign * RAIL_INNER, sign * RAIL_OUTER])          # [lower x, higher x]
    VX = pin_x[1] if RAIL_ORDER == "G+" else pin_x[0]               # x of the + pins
    GX = pin_x[0] if RAIL_ORDER == "G+" else pin_x[1]

    def P(x, y, rot=0, **k):
        dd = dict(x=sx + x, y=y, rot=rot)
        dd.update(k)
        return dd

    # --- buck power stage (IC native orientation: VIN/GND on the left, SW/BST on the right)
    IX, IY = -5.0, 6.0
    d.add(U_BUCK, "Regulator_Switching:TPS62933P", "TPS62933P",
          pins={"RT": None, "EN": n("EN"), "VIN": "VBUS", "GND": "GND", "SW": n("SW"), "BST": n("BST"),
                "PG": n("PG"), "FB": n("FB")},
          lcsc="C5219254", mpn="TPS62933PDRLR", group=g, desc="3.8-30 V in, 3 A sync buck, RT open = 500 kHz",
          pcb=P(IX, IY))
    d.add(C(0), "Device:C", "22uF 25V", C1206, pins={"1": "VBUS", "2": "GND"}, lcsc="C12891", group=g,
          pcb=P(IX - 4.2, IY + 0.5, 270))
    d.add(C(1), "Device:C", "100nF", C0402, pins={"1": "VBUS", "2": "GND"}, lcsc="C1525", group=g,
          pcb=P(IX - 2.3, IY + 0.5, 270))
    d.add(C(2), "Device:C", "100nF", C0402, pins={"1": n("BST"), "2": n("SW")}, lcsc="C1525", group=g,
          pcb=P(IX + 2.0, IY + 1.0, 270))
    d.add(IND, "Device:L", "4.7uH", "Inductor_SMD:L_Changjiang_FXL0630", pins={"1": n("SW"), "2": n("VPRE")},
          lcsc="C167220", mpn="FXL0630-4R7-M", group=g, desc="4.7 uH, 6 A sat, 33 mOhm", pcb=P(IX + 1.0, IY + 6.5, 270))
    for i, x in enumerate((0.7, 2.8, 4.9)):
        d.add(C(3 + i), "Device:C", "22uF 10V", C0805, pins={"1": n("VPRE"), "2": "GND"}, lcsc="C29277",
              group=g, pcb=P(x, 14.0, 90))
    d.add(R(0), "Device:R", "50m", "Resistor_SMD:R_1206_3216Metric", pins={"1": n("VPRE"), "2": n("OUT")},
          lcsc="C127691", group=g, desc="current shunt 50 mOhm 1%", pcb=P(8.4, 15.5, 0))
    d.add(C(6), "Device:C", "10uF", C0603, pins={"1": n("OUT"), "2": "GND"}, lcsc="C19702", group=g,
          desc="output cap at the rail pins", pcb=P(VX - sx, 47.6, 270))
    # --- enable / power good
    d.add(R(9), "Device:R", "100k", R0402, pins={"1": "+3V3", "2": n("EN")}, lcsc="C25741", group=g,
          pcb=P(-7.0, 2.6, 270))
    d.add(R(10), "Device:R", "100k", R0402, pins={"1": "+3V3", "2": n("PG")}, lcsc="C25741", group=g,
          pcb=P(-2.0, 3.6, 0))
    # --- current monitor
    d.add(U_INA, "multivolt:INA301", "INA301A1",
          pins={"1": "+3V3", "2": n("ISNS"), "3": n("LIM"), "4": "GND", "5": "RST", "6": n("EN"),
                "7": n("SNM"), "8": n("SNP")},
          lcsc="C471062", mpn="INA301A1IDGKR", group=g, desc="gain 20: 1 V/A on the 50 mOhm shunt",
          pcb=P(6.8, 22.6))
    # input filter (INA301 datasheet): 2 x 10R + 4.7uF -> ~94 us, so cap inrush doesn't latch a trip
    d.add(R(15), "Device:R", "10", R0402, pins={"1": n("VPRE"), "2": n("SNP")}, lcsc="C25077", group=g,
          pcb=P(8.3, 17.8, 270))
    d.add(R(16), "Device:R", "10", R0402, pins={"1": n("OUT"), "2": n("SNM")}, lcsc="C25077", group=g,
          pcb=P(9.6, 17.8, 270))
    d.add(C(8), "Device:C", "4.7uF", C0402, pins={"1": n("SNP"), "2": n("SNM")}, lcsc="C106859", group=g,
          desc="differential filter cap", pcb=P(8.95, 19.6, 0))
    # bleeder: rail drops to the new (lower) voltage in ~35 ms (buck can't sink current)
    d.add(R(17), "Device:R", "1k", R0402, pins={"1": n("OUT"), "2": "GND"}, lcsc="C11702", group=g,
          desc="output bleeder, 25 mW at 5 V", pcb=P(VX - sx, 50.6, 270))
    d.add(C(7), "Device:C", "100nF", C0402, pins={"1": "+3V3", "2": "GND"}, lcsc="C1525", group=g,
          pcb=P(2.6, 21.8, 270))
    d.add(R(11), "Device:R", "24.9k", R0402, pins={"1": n("LIM"), "2": "GND"}, lcsc="C138027", group=g,
          desc="LIMIT: 80 uA x 24.9k = 2.0 V = 2 A", pcb=P(3.4, 25.9, 0))
    d.add(R(12), "Device:R", "24.9k", R0402, pins={"1": n("LIM"), "2": n("LIMJ")}, lcsc="C138027", group=g,
          desc="paralleled by ILIM jumper: 12.45k = 1 A", pcb=P(3.4, 27.1, 0))
    d.add("J%d" % (base + 1), "Connector_Generic:Conn_01x02", "ILIM 1A", HDR + "PinHeader_1x02_P2.54mm_Vertical",
          pins={"1": n("LIMJ"), "2": "GND"}, lcsc="C492401", group=g, desc="fit jumper = 1 A trip, open = 2 A",
          pcb=P(9.4, 27.0))
    d.add("TP%d" % base, "Connector:TestPoint", "ISNS", "TestPoint:TestPoint_Pad_D1.5mm",
          pins={"1": n("ISNS")}, group=g, in_bom=False, desc="INA301 output, 1 V/A", pcb=P(5.8, 28.4))
    # --- voltage select string + jumper header
    nets = [n("OUT")] + [n("T%d" % (i + 1)) for i in range(6)] + ["GND"]
    for i, (val, lc) in enumerate(FB_STRING):
        d.add(R(1 + i), "Device:R", val, R0402, pins={"1": nets[i], "2": nets[i + 1]}, lcsc=lc, group=g,
              pcb=P(0.6, 26.0 + i * 2.0, 270))
    d.add(R(8), "Device:R", "1M", R0402, pins={"1": "+3V3", "2": n("FB")}, lcsc="C26083", group=g,
          desc="no jumper -> FB high -> converter idles", pcb=P(-10.4, 24.6, 270))
    jp = {}
    for i in range(6):
        jp[str(2 * i + 1)] = n("FB")
        jp[str(2 * i + 2)] = n("T%d" % (i + 1))
    d.add("J%d" % base, "Connector_Generic:Conn_02x06_Odd_Even", "VSEL", HDR + "PinHeader_2x06_P2.54mm_Vertical",
          pins=jp, lcsc="C492423", group=g, desc="one jumper per rail: row picks the voltage",
          pcb=P(-7.6, 24.6))
    for i, t in enumerate(TAPS):
        texts.append(dict(text=t, x=sx - 1.6, y=24.6 + i * 2.54, size=0.9, thick=0.16))
    texts.append(dict(text="VSEL " + s, x=sx - 6.3, y=22.4, size=0.9, thick=0.16))
    # --- LEDs
    d.add("D%d" % base, "Device:LED", "OK", LED0603, pins={"K": n("OKK"), "A": n("OKA")}, lcsc="C2289",
          mpn="KT-0603YG", group=g, pcb=P(-8.6, 39.9))
    d.add(R(13), "Device:R", "330", R0402, pins={"1": "+3V3", "2": n("OKA")}, lcsc="C25104", group=g,
          pcb=P(-8.6, 41.3))
    d.add("D%d" % (base + 1), "Device:LED", "OC", LED0603, pins={"K": n("EN"), "A": n("OCA")}, lcsc="C2286",
          mpn="KT-0603R", group=g, desc="lit = overcurrent latched", pcb=P(-4.2, 39.9))
    d.add(R(14), "Device:R", "1k", R0402, pins={"1": "+3V3", "2": n("OCA")}, lcsc="C11702", group=g,
          pcb=P(-4.2, 41.3))
    texts.append(dict(text="OK", x=sx - 8.6, y=38.85, size=0.7))
    texts.append(dict(text="OC", x=sx - 4.2, y=38.85, size=0.7))
    texts.append(dict(text="1A", x=sx + 9.4, y=25.4, size=0.8))
    texts.append(dict(text="I", x=sx + 5.8, y=30.2, size=0.7))
    texts.append(dict(text="RAIL " + s, x=sx, y=1.6, size=1.1, thick=0.2))
    # --- rail headers: two 2-pin headers per side, 5 holes apart along the rail (bottom side, pins down)
    for j, y in enumerate(RAIL_ROW_Y):
        ref = "J%d" % (base + 2 + j)
        # rotated 270 on the bottom side: pad 1 at the lower x, pad 2 at +2.54 mm
        pins = {"1": "GND" if RAIL_ORDER == "G+" else n("OUT"), "2": n("OUT") if RAIL_ORDER == "G+" else "GND"}
        d.add(ref, "Connector_Generic:Conn_01x02", "RAIL %s" % s, HDR + "PinHeader_1x02_P2.54mm_Vertical",
              pins=pins, lcsc="C492401", group="Outputs",
              desc="breadboard rail pins (mount on bottom, pins down)", pcb=dict(x=pin_x[0], y=y, rot=270, side="B"))
    texts.append(dict(text="+", x=VX, y=44.4, size=0.9))
    texts.append(dict(text="G", x=GX, y=44.4, size=0.8))

    # --- pre-routed power paths (pad references resolved by pcbgen)
    U = U_BUCK
    tracks += [
        # VIN: pin 3 -> 100n -> 22u ; GND: pin 4 -> 100n -> 22u
        dict(net="VBUS", width=0.3, pts=[U + ".3", [sx + IX - 1.95, IY + 0.25], C(1) + ".1"]),
        dict(net="VBUS", width=0.6, pts=[C(1) + ".1", C(0) + ".1"]),
        dict(net="GND", width=0.3, pts=[U + ".4", [sx + IX - 1.95, IY + 0.75], C(1) + ".2"]),
        dict(net="GND", width=0.6, pts=[C(1) + ".2", C(0) + ".2"]),
        # EN escapes upward between RT and the 100n, to its pull-up
        dict(net=n("EN"), width=0.25, pts=[U + ".2", [sx + IX - 1.5, IY - 0.25], [sx + IX - 1.5, IY - 2.5], R(9) + ".2"]),
        # SW: pin 5 -> inductor ; bootstrap cap
        dict(net=n("SW"), width=0.3, pts=[U + ".5", [U + ".5", 0, 0.55]]),
        dict(net=n("SW"), width=1.0, pts=[[U + ".5", 0, 0.55], [IND + ".1", -0.26, -0.6]]),
        dict(net=n("SW"), width=0.4, pts=[C(2) + ".2", [C(2) + ".2", 0, 1.0]]),
        dict(net=n("BST"), width=0.3, pts=[U + ".6", [U + ".6", 0.55, 0], C(2) + ".1"]),
        # VPRE: inductor -> output caps -> shunt
        dict(net=n("VPRE"), width=1.0, pts=[IND + ".2", C(3) + ".1", C(4) + ".1", C(5) + ".1", R(0) + ".1"]),
    ]
    # --- output: shunt -> INA Kelvin -> FB string -> edge trunk -> rail pins / aux header
    TX = sx + 10.8                       # trunk x
    rails = ["J%d" % (base + 2 + j) for j in range(2)]
    vpad = "2" if RAIL_ORDER == "G+" else "1"
    YB = 45.8                            # output bus y (between the rail-pin rows)
    tracks += [
        # Kelvin sense through the filter
        dict(net=n("VPRE"), width=0.3, pts=[R(0) + ".1", [R(0) + ".1", 0, 1.1], R(15) + ".1"]),
        dict(net=n("SNP"), width=0.3, pts=[R(15) + ".2", C(8) + ".1", [sx + 8.91, 20.6], U_INA + ".8"]),
        dict(net=n("OUT"), width=0.3, pts=[R(0) + ".2", R(16) + ".1"]),
        dict(net=n("SNM"), width=0.25, pts=[R(16) + ".2", C(8) + ".2", [sx + 10.1, 20.3], [sx + 10.1, 22.275], U_INA + ".7"]),
        dict(net=n("OUT"), width=0.8, pts=[R(0) + ".2", [TX, 16.44], [TX, YB]]),
        dict(net=n("OUT"), width=0.25, pts=[[TX, 24.9], [sx + 0.6, 24.9], R(1) + ".1"]),
        # bus -> + pins (upper row on top, lower row via the bottom layer) and the output cap
        dict(net=n("OUT"), width=0.8, pts=[[TX, YB], [VX, YB]]),
        dict(net=n("OUT"), width=0.8, pts=[rails[0] + "." + vpad, [VX, YB], C(6) + ".1"]),
        dict(net=n("OUT"), width=0.8, layer="B.Cu", pts=[rails[0] + "." + vpad, rails[1] + "." + vpad]),
        # bus -> AUX header
        dict(net=n("OUT"), width=0.8, pts=[[TX, YB], [-3.81 if s == "L" else 3.81, YB], "J2.1" if s == "L" else "J2.4"]),
    ]
    vias += [
        dict(net=n("EN"), x=sx + IX - 1.5, y=IY - 2.5),
        dict(net="GND", at=[C(0) + ".2", 0, 1.3]),
        dict(net="GND", at=[C(0) + ".2", -1.0, 1.3]),
        dict(net="GND", at=[C(1) + ".2", 0, 0.9]),
    ] + [dict(net="GND", at=[C(k) + ".2", 0, -1.1]) for k in (3, 4, 5)]
    tracks += [
        dict(net="GND", width=0.6, pts=[C(0) + ".2", [C(0) + ".2", 0, 1.3]]),
        dict(net="GND", width=0.4, pts=[C(1) + ".2", [C(1) + ".2", 0, 0.9]]),
        dict(net="VBUS", width=0.8, pts=[C(0) + ".1", [C(0) + ".1", 0, -1.3]]),
    ] + [dict(net="GND", width=0.6, pts=[C(k) + ".2", [C(k) + ".2", 0, -1.1]]) for k in (3, 4, 5)]

    d.note(g, "TPS62933P: RT open -> 500 kHz, fixed 2 ms soft start. FB string taps (top->bottom):\n"
              "6.34k / 2.43k / 1.62k / 2.26k / 1.4k / 1.5k / 2.94k (E96 1%), plus 1M FB->3V3.\n"
              "Computed outputs: 1.202 / 1.500 / 1.800 / 2.501 / 3.296 / 4.992 V (tools/fb_string.py).")


if __name__ == "__main__":
    dd = build()
    for p in dd.check():
        print("WARN", p)
