#!/bin/sh
# Optional experimental extra only. No service restart or printer operations.
set -eu
if [ "$#" -gt 1 ]; then
    echo "Usage: $0 [Klipper-or-Kalico-source-directory]" >&2
    exit 2
fi
firmware_dir=${1:-"$HOME/klipper"}
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source_file="$source_dir/kat_beacon_temperature.py"
target="$firmware_dir/klippy/extras/kat_beacon_temperature.py"
if [ ! -d "$firmware_dir/klippy/extras" ]; then
    echo "No Klipper/Kalico extras directory: $firmware_dir/klippy/extras" >&2
    exit 1
fi
if [ -e "$target" ] || [ -L "$target" ]; then
    if [ -L "$target" ] && [ "$(readlink "$target")" = "$source_file" ]; then
        echo "Experimental KAT extra already linked."
        exit 0
    fi
    echo "Refusing to replace an existing file/link: $target" >&2
    exit 1
fi
ln -s "$source_file" "$target"
echo "Installed experimental extra. Read README.md, add its config section, and restart only while idle."
