#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
#  setup_third_party.sh
#  Clone third-party repositories into ./third_party/
#  Usage: bash scripts/setup_third_party.sh
# ──────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
THIRD="$ROOT/third_party"

mkdir -p "$THIRD"

# ── Repository list ──────────────────────────────────────────
declare -A REPOS=(
    ["Raster2Seq"]="https://github.com/Cornell-VAILab/Raster2Seq.git"
    ["planparser"]="https://github.com/anngrrr/planparser.git"
    ["mlsd"]="https://github.com/navervision/mlsd.git"
    ["floorplan-detection"]="https://github.com/Daigo-Kanda/floorplan-detection.git"
    ["Img2CADSeq"]="https://github.com/Rilpraa0110/Img2CADSeq.git"
)

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Third-Party Repository Setup"
echo "═══════════════════════════════════════════════════"
echo ""

for name in "${!REPOS[@]}"; do
    dest="$THIRD/$name"
    url="${REPOS[$name]}"
    if [ -d "$dest" ]; then
        echo "[SKIP] $name — already exists at $dest"
    else
        echo "[CLONE] $name ← $url"
        if git clone --depth 1 "$url" "$dest"; then
            echo "[OK] $name cloned successfully"
        else
            echo "[ERROR] Failed to clone $name"
        fi
    fi
done

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Summary"
echo "═══════════════════════════════════════════════════"

for name in "${!REPOS[@]}"; do
    dest="$THIRD/$name"
    if [ -d "$dest" ]; then
        count=$(find "$dest" -type f | wc -l)
        echo "  ✓ $name ($count files)"
    else
        echo "  ✗ $name — MISSING"
    fi
done

echo ""
