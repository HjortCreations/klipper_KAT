#!/usr/bin/env bash
set -euo pipefail

######################################################################
# KAT - GENERATE INPUT SHAPER GRAPH Y
#
# Finds the newest /tmp/resonances_y_*.csv file and generates a PNG
# using Klipper's calibrate_shaper.py script.
######################################################################

SCRIPT_DIR="$(cd -- "$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")" >/dev/null 2>&1 && pwd)"
source "${SCRIPT_DIR}/kat-common.sh"

report_status "Generating Y input shaper graph"

ensure_output_dir

CALIBRATE_SHAPER="${KAT_KLIPPER_DIR}/scripts/calibrate_shaper.py"
require_klipper_script "${CALIBRATE_SHAPER}"

NEWY="$(newest_matching_file 'resonances_y_*.csv')"
DATE="$(date +'%Y-%m-%d-%H%M%S')"
OUTPUT="${KAT_OUTPUT_DIR}/resonances_y_${DATE}.png"

echo "Using CSV:"
echo "${NEWY}"
echo ""
echo "Output:"
echo "${OUTPUT}"

"${CALIBRATE_SHAPER}" "${NEWY}" -o "${OUTPUT}"

if [ "${EUID}" -eq 0 ]; then
    chown "${KAT_USERNAME}:${KAT_USERGROUP}" "${OUTPUT}" || true
fi

print_result "${OUTPUT}"
