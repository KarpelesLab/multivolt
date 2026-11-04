#!/bin/bash
# Fabrication outputs for JLCPCB: gerbers+drill zip, BOM, CPL, schematic PDF, renders.
# usage: tools/fab.sh <boardname>
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
K=$ROOT/tools/kcli
KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
[ -x "$KP" ] || KP=python3   # Linux: system python with pcbnew
N=$1
B=$ROOT/boards/$N
O=$B/fab
rm -rf $O; mkdir -p $O/gerbers
cd $B
$K pcb export gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
    --subtract-soldermask --no-x2 -o $O/gerbers/ $N.kicad_pcb >/dev/null
$K pcb export drill --format excellon --excellon-separate-th --excellon-units mm -o $O/gerbers/ $N.kicad_pcb >/dev/null
(cd $O/gerbers && zip -q ../${N}_gerbers.zip *)
$K pcb export pos --format csv --units mm --side both -o $O/${N}_pos_kicad.csv $N.kicad_pcb >/dev/null
$KP $ROOT/tools/jlc_files.py $N.design.json $O/${N}_pos_kicad.csv $O $N.kicad_pcb
$K sch export pdf -o $O/${N}_schematic.pdf $N.kicad_sch >/dev/null
$K pcb render --quality high --side top -w 1600 -h 1200 --background opaque -o $O/${N}_top.png $N.kicad_pcb >/dev/null 2>&1 || true
$K pcb render --quality high --side bottom -w 1600 -h 1200 --background opaque -o $O/${N}_bottom.png $N.kicad_pcb >/dev/null 2>&1 || true
$K pcb render --quality high --rotate '-40,0,30' --perspective -w 1600 -h 1200 --background opaque -o $O/${N}_iso.png $N.kicad_pcb >/dev/null 2>&1 || true
ls -la $O
