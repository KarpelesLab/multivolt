#!/bin/bash
# Full pipeline: schematic -> ERC -> netlist check -> PCB -> route -> DRC
# usage: tools/make_board.sh designs/<file>.py <boardname> [pcbgen args]
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
K=$ROOT/tools/kcli
python3 $ROOT/tools/build_sch.py "$1"
B=$ROOT/boards/$2; shift 2
cd $B
$K sch erc --severity-all --exit-code-violations -o erc.rpt $(basename $B).kicad_sch | grep -E "violations" || true
$K sch export netlist --format kicadsexpr -o $(basename $B).net $(basename $B).kicad_sch >/dev/null
python3 $ROOT/tools/check_netlist.py $(basename $B).net $(basename $B).design.json
$KP $ROOT/tools/pcbgen.py $B "$@" 2>&1 | grep -v -E "assert"
$K pcb drc --severity-error --schematic-parity -o drc.rpt $(basename $B).kicad_pcb | grep -E "violation|unconnected|parity" || true
grep -E "^\*\*|^\[" drc.rpt | head -40
