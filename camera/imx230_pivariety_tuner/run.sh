#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(
    cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
    pwd
)"

if [[ ${EUID} -ne 0 ]]; then
    exec sudo \
        --preserve-env=T3_EDGEAI_ENV,IMX230_GST_PLUGIN_DIR,IMX230_TIOVX_LIB_DIR,IMX230_DCC_DIR,IMX230_PYTHON,IMX230_MEDIA_DEVICE,IMX230_VIDEO_DEVICE,IMX230_SENSOR_DEVICE,IMX230_SETTINGS_FILE,IMX230_SNAPSHOT_DIR,IMX230_HOST,IMX230_PORT,IMX230_GST_REGISTRY \
        -- "$0" "$@"
fi

EDGEAI_ENV="${T3_EDGEAI_ENV:-/opt/t3-edgeai-env}"

if [[ ! -r "$EDGEAI_ENV" ]]; then
    echo "Error: T3 Edge AI environment file not found: $EDGEAI_ENV" >&2
    exit 1
fi

# shellcheck disable=SC1090
source "$EDGEAI_ENV"
unset LD_PRELOAD

if [[ -n ${IMX230_GST_PLUGIN_DIR:-} ]]; then
    export GST_PLUGIN_PATH="${IMX230_GST_PLUGIN_DIR}${GST_PLUGIN_PATH:+:${GST_PLUGIN_PATH}}"
fi

if [[ -n ${IMX230_TIOVX_LIB_DIR:-} ]]; then
    export LD_LIBRARY_PATH="${IMX230_TIOVX_LIB_DIR}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
fi

export IMX230_DCC_DIR="${IMX230_DCC_DIR:-/opt/imaging/imx230/linear}"
export GST_REGISTRY="${IMX230_GST_REGISTRY:-/tmp/gst-registry-imx230-tuner.bin}"

rm -f "$GST_REGISTRY"

PYTHON="${IMX230_PYTHON:-${SCRIPT_DIR}/venv/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
    PYTHON="$(command -v python3 || true)"
fi

if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
    echo "Error: no usable Python interpreter was found." >&2
    exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/app.py"
