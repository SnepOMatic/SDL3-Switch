#!/usr/bin/env bash
#
# build-switch.sh
# Cross-compile this SDL3 fork as a STATIC library for the Nintendo Switch
# (devkitA64 / libnx) and install it into DevKitPro's Switch portlibs, so that
# other projects can pick it up with find_package(SDL3) under the Switch toolchain.
#
# This is a local build helper for your own workflow - it is NOT part of the
# SDL3 source tree. Feel free to gitignore it.
#
# Usage:
#     ./build-switch.sh                 # configure, build, install
#     CLEAN=1 ./build-switch.sh         # wipe the build dir first (recommended
#                                       # after pulling a big upstream merge)
#     BUILD_TYPE=Debug ./build-switch.sh
#     SDL_ARMSVE2=ON ./build-switch.sh  # force-enable SVE2 (off by default; see note)
#
# Environment overrides:
#     DEVKITPRO     install root         (default: /opt/devkitpro)
#     BUILD_TYPE    Release | Debug      (default: Release)
#     JOBS          parallel build jobs  (default: nproc)
#     CLEAN         1 = remove build dir before configuring
#     SDL_ARMSVE2   ON | OFF             (default: OFF - see note below)
#
set -euo pipefail

# --- locate DevKitPro -------------------------------------------------------
: "${DEVKITPRO:=/opt/devkitpro}"
if [ ! -d "$DEVKITPRO" ]; then
  echo "error: DevKitPro not found at '$DEVKITPRO'." >&2
  echo "       Set DEVKITPRO to your install, e.g. 'export DEVKITPRO=/opt/devkitpro'." >&2
  exit 1
fi

TOOLCHAIN="$DEVKITPRO/cmake/Switch.cmake"
PORTLIBS="$DEVKITPRO/portlibs/switch"
if [ ! -f "$TOOLCHAIN" ]; then
  echo "error: Switch toolchain not found at '$TOOLCHAIN'." >&2
  echo "       Install the 'switch-dev' group with (dkp-)pacman." >&2
  exit 1
fi

# --- paths / options --------------------------------------------------------
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # SDL3 fork root
BUILD_DIR="$SRC_DIR/build-switch"
BUILD_TYPE="${BUILD_TYPE:-Release}"
JOBS="${JOBS:-$(nproc 2>/dev/null || echo 4)}"
SDL_ARMSVE2="${SDL_ARMSVE2:-OFF}"

# Prefer Ninja if available, otherwise fall back to Makefiles.
GEN_ARGS=()
if command -v ninja >/dev/null 2>&1; then
  GEN_ARGS=(-G Ninja)
fi

if [ "${CLEAN:-0}" = "1" ]; then
  echo ">> CLEAN=1: removing $BUILD_DIR"
  rm -rf "$BUILD_DIR"
fi

echo ">> SDL3 source : $SRC_DIR"
echo ">> DevKitPro   : $DEVKITPRO"
echo ">> Build type  : $BUILD_TYPE  (jobs: $JOBS)"
echo ">> Install to  : $PORTLIBS"
echo ">> SDL_ARMSVE2 : $SDL_ARMSVE2"

# --- configure --------------------------------------------------------------
cmake -S "$SRC_DIR" -B "$BUILD_DIR" "${GEN_ARGS[@]}" \
  -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN" \
  -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
  -DCMAKE_INSTALL_PREFIX="$PORTLIBS" \
  -DCMAKE_DISABLE_PRECOMPILE_HEADERS:BOOL=ON \
  -DSDL_STATIC=ON \
  -DSDL_DUMMYVIDEO=OFF \
  -DSDL_SHARED=OFF \
  -DSDL_TESTS=OFF \
  -DSDL_EXAMPLES=OFF \
  -DSDL_ARMSVE2="$SDL_ARMSVE2"

# --- build ------------------------------------------------------------------
cmake --build "$BUILD_DIR" --parallel "$JOBS"

# --- install ----------------------------------------------------------------
# portlibs may be root-owned on a system-wide install; retry with sudo if so.
if [ -w "$PORTLIBS" ] || [ ! -e "$PORTLIBS" ]; then
  cmake --install "$BUILD_DIR"
else
  echo ">> $PORTLIBS not writable, retrying install with sudo"
  sudo cmake --install "$BUILD_DIR"
fi

echo ""
echo ">> Done. Static SDL3 installed under $PORTLIBS"
echo ">> In your project's CMakeLists.txt (built with the Switch toolchain):"
echo ">>     find_package(SDL3 REQUIRED CONFIG)"
echo ">>     target_link_libraries(your_target PRIVATE SDL3::SDL3-static)"
