#!/usr/bin/env bash
set -euo pipefail

######################################################################
# KAT - GENERATE INPUT SHAPER GRAPH X
#
# Finds the newest /tmp/resonances_x_*.csv file and generates a PNG
# using Klipper's calibrate_shaper.py script.
######################################################################

SCRIPT_DIR="$(cd -- "$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")" >/dev/null 2>&1 && pwd)"
source "${SCRIPT_DIR}/kat-common.sh"

report_status "Generating X input shaper graph"

ensure_output_dir

CALIBRATE_SHAPER="${KAT_KLIPPER_DIR}/scripts/calibrate_shaper.py"
require_klipper_script "${CALIBRATE_SHAPER}"

NEWX="$(newest_matching_file 'resonances_x_*.csv')"
DATE="$(date +'%Y-%m-%d-%H%M%S')"
OUTPUT="${KAT_OUTPUT_DIR}/resonances_x_${DATE}.png"

echo "Using CSV:"
echo "${NEWX}"
echo ""
echo "Output:"
echo "${OUTPUT}"

"${CALIBRATE_SHAPER}" "${NEWX}" -o "${OUTPUT}"

if [ "${EUID}" -eq 0 ]; then
    chown "${KAT_USERNAME}:${KAT_USERGROUP}" "${OUTPUT}" || true
fi

print_result "${OUTPUT}"
