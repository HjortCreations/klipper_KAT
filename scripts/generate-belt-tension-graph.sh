#!/usr/bin/env bash
set -euo pipefail

######################################################################
# KAT - GENERATE BELT TENSION GRAPH
#
# Finds the newest upper/lower belt tension CSV files in /tmp and
# generates a combined PNG using Klipper's graph_accelerometer.py script.
#
# Expected CSV patterns:
# - /tmp/raw_data_axis*_belt-tension-upper.csv
# - /tmp/raw_data_axis*_belt-tension-lower.csv
######################################################################

SCRIPT_DIR="$(cd -- "$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")" >/dev/null 2>&1 && pwd)"
source "${SCRIPT_DIR}/kat-common.sh"

report_status "Generating belt tension graph"

# TEST_RESONANCES can return before CSV writing is fully complete.
# Waiting a little keeps this simple and reliable.
sleep 10

ensure_output_dir

GRAPH_ACCELEROMETER="${KAT_KLIPPER_DIR}/scripts/graph_accelerometer.py"
require_klipper_script "${GRAPH_ACCELEROMETER}"

NEWUPPER="$(newest_matching_file 'raw_data_axis*_belt-tension-upper.csv')"
NEWLOWER="$(newest_matching_file 'raw_data_axis*_belt-tension-lower.csv')"
DATE="$(date +'%Y-%m-%d-%H%M%S')"
OUTPUT="${KAT_OUTPUT_DIR}/belt-tension-resonances_${DATE}.png"

echo "Using lower CSV:"
echo "${NEWLOWER}"
echo ""
echo "Using upper CSV:"
echo "${NEWUPPER}"
echo ""
echo "Output:"
echo "${OUTPUT}"

run_klipper_python_script "${GRAPH_ACCELEROMETER}" -c "${NEWLOWER}" "${NEWUPPER}" -o "${OUTPUT}"

if [ "${EUID}" -eq 0 ]; then
    chown "${KAT_USERNAME}:${KAT_USERGROUP}" "${OUTPUT}" || true
fi

print_result "${OUTPUT}"
