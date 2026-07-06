#!/usr/bin/env bash
set -euo pipefail

######################################################################
# KAT - GENERATE RESONANCE GRAPH Z
#
# Finds the newest /tmp/resonances_z_*.csv file and generates a PNG
# using Klipper's graph_accelerometer.py script.
#
# This is not an input shaper calibration graph.
# It is a general resonance / accelerometer graph for Z.
######################################################################

SCRIPT_DIR="$(cd -- "$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")" >/dev/null 2>&1 && pwd)"
source "${SCRIPT_DIR}/kat-common.sh"

report_status "Generating Z resonance graph"

ensure_output_dir

GRAPH_ACCELEROMETER="${KAT_KLIPPER_DIR}/scripts/graph_accelerometer.py"
require_klipper_script "${GRAPH_ACCELEROMETER}"

NEWZ="$(newest_matching_file 'resonances_z_*.csv')"
DATE="$(date +'%Y-%m-%d-%H%M%S')"
OUTPUT="${KAT_OUTPUT_DIR}/resonances_z_${DATE}.png"

echo "Using CSV:"
echo "${NEWZ}"
echo ""
echo "Output:"
echo "${OUTPUT}"

"${KAT_PYTHON}" "${GRAPH_ACCELEROMETER}" -c "${NEWZ}" -o "${OUTPUT}"

if [ "${EUID}" -eq 0 ]; then
    chown "${KAT_USERNAME}:${KAT_USERGROUP}" "${OUTPUT}" || true
fi

print_result "${OUTPUT}"
