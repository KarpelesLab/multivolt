#!/bin/bash
# Download the autorouter toolchain into tools/bin (macOS arm64): Freerouting 2.5.0 + Temurin Java 25 JRE.
set -e
cd "$(dirname "$0")"; mkdir -p bin; cd bin
[ -f freerouting.jar ] || curl -sL -o freerouting.jar https://github.com/freerouting/freerouting/releases/download/v2.5.0/freerouting-2.5.0.jar
if [ ! -x java ]; then
  curl -sL -o jre.tgz "https://api.adoptium.net/v3/binary/latest/25/ga/mac/aarch64/jre/hotspot/normal/eclipse"
  tar xzf jre.tgz && rm jre.tgz
  ln -sf "$(ls -d jdk-25*)/Contents/Home/bin/java" java
fi
./java -version 2>&1 | head -1
