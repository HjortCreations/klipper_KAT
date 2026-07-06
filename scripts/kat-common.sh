#!/usr/bin/env bash
set -euo pipefail

######################################################################
# KAT COMMON SCRIPT HELPERS
#
# Shared shell helper for KAT resonance tooling scripts.
#
# Environment variables can be overridden before running a script:
# - KAT_USERNAME
# - KAT_USERGROUP
# - KAT_PRINTER_DATA_DIR
# - KAT_KLIPPER_DIR
# - KAT_OUTPUT_DIR
# - KAT_PYTHON
#
# Default assumptions:
# - ~/printer_data
# - ~/klipper or ~/kalico
# - ~/printer_data/config/input_shaper
######################################################################

######################################################################
# Resolve real user and home directory
######################################################################

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

######################################################################
# Resolve firmware source directory
#
# KAT works with both Klipper and Kalico.
# Users can override this manually by exporting KAT_KLIPPER_DIR.
######################################################################

detect_firmware_dir() {
    if [ -n "${KAT_KLIPPER_DIR:-}" ]; then
        echo "${KAT_KLIPPER_DIR}"
        return
    fi

    if [ -f "${REAL_HOME}/klipper/scripts/calibrate_shaper.py" ]; then
        echo "${REAL_HOME}/klipper"
        return
    fi

    if [ -f "${REAL_HOME}/kalico/scripts/calibrate_shaper.py" ]; then
        echo "${REAL_HOME}/kalico"
        return
    fi

    # Fallback to the common Klipper path.
    echo "${REAL_HOME}/klipper"
}

: "${KAT_USERNAME:=${REAL_USER}}"
: "${KAT_USERGROUP:=${KAT_USERNAME}}"
: "${KAT_PRINTER_DATA_DIR:=${REAL_HOME}/printer_data}"
: "${KAT_KLIPPER_DIR:=$(detect_firmware_dir)}"
: "${KAT_OUTPUT_DIR:=${KAT_PRINTER_DATA_DIR}/config/input_shaper}"

detect_python() {
    if [ -n "${KAT_PYTHON:-}" ]; then
        echo "${KAT_PYTHON}"
        return
    fi

    if [ -x "${REAL_HOME}/klippy-env/bin/python" ]; then
        echo "${REAL_HOME}/klippy-env/bin/python"
        return
    fi

    if [ -x "${REAL_HOME}/klipper-env/bin/python" ]; then
        echo "${REAL_HOME}/klipper-env/bin/python"
        return
    fi

    command -v python3
}

: "${KAT_PYTHON:=$(detect_python)}"

python_extra_path() {
    if [ -x "${KAT_PYTHON}" ]; then
        "${KAT_PYTHON}" -c 'import site; print(":".join(site.getsitepackages()))' 2>/dev/null || true
    fi
}

python_has_modules() {
    local python_path="$1"
    local extra_path="$2"
    shift 2

    if [ ! -x "${python_path}" ]; then
        return 1
    fi

    PYTHONPATH="${extra_path}${PYTHONPATH:+:${PYTHONPATH}}" "${python_path}" - "$@" <<'PY'
import importlib
import sys

missing = []
for module_name in sys.argv[1:]:
    try:
        importlib.import_module(module_name)
    except Exception:
        missing.append(module_name)

if missing:
    print(", ".join(missing), file=sys.stderr)
    sys.exit(1)
PY
}

run_klipper_python_script() {
    local script_path="$1"
    shift

    local extra_path
    local python3_path
    local candidate
    local candidates=()

    extra_path="$(python_extra_path)"
    candidates+=("${KAT_PYTHON}")
    candidates+=("/usr/bin/python3")

    python3_path="$(command -v python3 2>/dev/null || true)"
    if [ -n "${python3_path}" ]; then
        candidates+=("${python3_path}")
    fi

    for candidate in "${candidates[@]}"; do
        if python_has_modules "${candidate}" "${extra_path}" cffi numpy matplotlib; then
            PYTHONPATH="${extra_path}${PYTHONPATH:+:${PYTHONPATH}}" "${candidate}" "${script_path}" "$@"
            return
        fi
    done

    echo "ERROR: Could not find a Python environment with cffi, numpy, and matplotlib." >&2
    echo "Tried KAT_PYTHON=${KAT_PYTHON}, /usr/bin/python3, and python3." >&2
    echo "" >&2
    echo "Install Klipper resonance graph dependencies on the printer:" >&2
    echo "sudo apt update" >&2
    echo "sudo apt install python3-numpy python3-matplotlib libatlas-base-dev libopenblas-dev" >&2
    echo "~/klippy-env/bin/pip install -v \"numpy<1.26\"" >&2
    exit 1
}

######################################################################
# Console helpers
######################################################################

report_status() {
    echo ""
    echo "###### $1"
}

print_result() {
    local output="$1"

    echo ""
    echo "KAT graph generated:"
    echo "${output}"
    echo ""
    echo "Open the file from the Klipper/Mainsail config file browser if your UI exposes:"
    echo "${KAT_OUTPUT_DIR}"
}

######################################################################
# File and dependency helpers
######################################################################

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
        echo "ERROR: Required Klipper/Kalico script not found: ${script_path}" >&2
        echo "Detected KAT_KLIPPER_DIR: ${KAT_KLIPPER_DIR}" >&2
        echo "" >&2
        echo "Override example:" >&2
        echo "KAT_KLIPPER_DIR=/home/pi/klipper ./script-name.sh" >&2
        echo "KAT_KLIPPER_DIR=/home/pi/kalico ./script-name.sh" >&2
        exit 1
    fi
}

newest_matching_file() {
    local pattern="$1"
    local file

    file="$(find /tmp -name "${pattern}" -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -f2- -d' ')"

    if [ -z "${file}" ]; then
        echo "ERROR: No matching file found in /tmp for pattern: ${pattern}" >&2
        echo "" >&2
        echo "Make sure TEST_RESONANCES has completed before generating the graph." >&2
        exit 1
    fi

    echo "${file}"
}
