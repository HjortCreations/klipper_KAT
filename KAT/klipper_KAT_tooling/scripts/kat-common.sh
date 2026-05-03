#!/usr/bin/env bash
set -euo pipefail

######################################################################
# KAT COMMON SCRIPT HELPERS
#
# Shared shell helper for KAT tooling scripts.
#
# Environment variables can be overridden before running a script:
# - KAT_USERNAME
# - KAT_USERGROUP
# - KAT_PRINTER_DATA_DIR
# - KAT_KLIPPER_DIR
# - KAT_OUTPUT_DIR
#
# Default assumptions match a common Klipper/Moonraker setup:
# - ~/printer_data
# - ~/klipper
# - ~/printer_data/config/input_shaper
######################################################################

# Determine the real user and home directory, even when called through sudo.
if [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER:-}" != "root" ]; then
    REAL_USER="${SUDO_USER}"
    REAL_HOME="$(getent passwd "${SUDO_USER}" | cut -d: -f6)"
elif [ "${EUID}" -ne 0 ]; then
    REAL_USER="${USER:-$(whoami)}"
    REAL_HOME="${HOME:-$(eval echo "/home/${REAL_USER}")}"
else
    REAL_USER="pi"
    REAL_HOME="/home/pi"
fi

: "${KAT_USERNAME:=${REAL_USER}}"
: "${KAT_USERGROUP:=${KAT_USERNAME}}"
: "${KAT_PRINTER_DATA_DIR:=${REAL_HOME}/printer_data}"
: "${KAT_KLIPPER_DIR:=${REAL_HOME}/klipper}"
: "${KAT_OUTPUT_DIR:=${KAT_PRINTER_DATA_DIR}/config/input_shaper}"

report_status() {
    echo ""
    echo "###### $1"
}

ensure_output_dir() {
    if [ ! -d "${KAT_OUTPUT_DIR}" ]; then
        mkdir -p "${KAT_OUTPUT_DIR}"
    fi

    # Only change ownership when running as root.
    if [ "${EUID}" -eq 0 ]; then
        chown "${KAT_USERNAME}:${KAT_USERGROUP}" "${KAT_OUTPUT_DIR}" || true
    fi
}

require_klipper_script() {
    local script_path="$1"

    if [ ! -f "${script_path}" ]; then
        echo "ERROR: Required Klipper script not found: ${script_path}" >&2
        echo "Check KAT_KLIPPER_DIR. Current value: ${KAT_KLIPPER_DIR}" >&2
        exit 1
    fi
}

newest_matching_file() {
    local pattern="$1"
    local file

    file="$(find /tmp -name "${pattern}" -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -f2- -d' ')"

    if [ -z "${file}" ]; then
        echo "ERROR: No matching file found in /tmp for pattern: ${pattern}" >&2
        exit 1
    fi

    echo "${file}"
}
