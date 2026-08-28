#!/usr/bin/env bash
# Build this tree with -DDISASMTRACE (F9 snapshots, EXEC/WATCH log).
#
#   tools/disasm/build-cocoamsx.sh
#
# Output: generated/cocoamsx-dd/Build/Products/Debug/CocoaMSX.app  (gitignored)
set -euo pipefail
src="$(cd "$(dirname "$0")/../.." && pwd)"
if [ ! -f "$src/CocoaMSX.xcodeproj/project.pbxproj" ]; then
    echo "CocoaMSX sources not found at $src" >&2
    exit 1
fi

xcodebuild -scheme CocoaMSX -configuration Debug \
  -project "$src/CocoaMSX.xcodeproj" \
  -derivedDataPath "$src/generated/cocoamsx-dd" \
  MACOSX_DEPLOYMENT_TARGET=11.0 \
  GCC_PREPROCESSOR_DEFINITIONS='$(inherited) DISASMTRACE fdopen=fdopen' \
  OTHER_CPLUSPLUSFLAGS='$(inherited) -Wno-c++11-narrowing' \
  CODE_SIGNING_ALLOWED=NO \
  EXCLUDED_SOURCE_FILE_NAMES='cocoamsx.iconset' \
  build

app="$src/generated/cocoamsx-dd/Build/Products/Debug/CocoaMSX.app"
echo "built: $app"
