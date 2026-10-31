#!/bin/bash
# render.sh <board.kicad_pcb> <out.png> [side F|B] [width]
K=$(dirname "$0")/kcli
S=${3:-F}; W=${4:-1600}
T=$(mktemp -d)
if [ "$S" = F ]; then L="F.Cu,F.SilkS,F.Mask,Edge.Cuts"; M=""; else L="B.Cu,B.SilkS,Edge.Cuts"; M="--mirror"; fi
$K pcb export svg --mode-single --fit-page-to-board --exclude-drawing-sheet $M -l $L -o $T/b.svg "$1" >/dev/null
rsvg-convert -w $W -b white $T/b.svg -o "$2"
