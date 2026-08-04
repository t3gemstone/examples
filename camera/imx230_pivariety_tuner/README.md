# Arducam Pivariety IMX230 Tuner

Browser-based live preview and camera tuning example for the Arducam Pivariety IMX230 camera on T3 Gemstone O1.

## Validated image path

```text
Arducam Pivariety IMX230
        |
        v
SRGGB10_1X10
        |
        v
V4L2 RG10
        |
        v
GStreamer rggb10
        |
        v
tiovxisp
        |
        v
IMX230 DCC profile
        |
        v
RGB live preview
```

## Validated hardware

- Board: T3 Gemstone O1
- Camera: Arducam B0324 / Pivariety IMX230, UC-788 Rev.B
- Connector: CSI0/J11
- CSI interface: 2-lane MIPI CSI-2
- Resolution: 1920x1080
- Kernel: 6.12.24-ti
- Horizontal flip: disabled
- Vertical flip: disabled

## Validated camera format

```text
Media bus: SRGGB10_1X10
V4L2:      RG10
GStreamer: rggb10
Resolution: 1920x1080
```

BGGR is not used by the validated IMX230 pipeline.

## Integration components

### Linux kernel and Device Tree

T3 Gemstone Linux PR:

https://github.com/t3gemstone/linux/pull/14

Provides:

- Arducam Pivariety V4L2 driver integration
- T3 Gemstone O1 CSI0/J11 Device Tree overlay
- Kernel Kconfig and Makefile integration

### GStreamer / TIOVX ISP support

Texas Instruments `edgeai-gst-plugins` PR:

https://github.com/TexasInstruments/edgeai-gst-plugins/pull/383

Provides:

- `SENSOR_SONY_IMX230_PIVARIETY` support
- IMX230 AE parameters
- Exposure and analogue-gain mapping used by `tiovxisp`

### TIOVX sensor-to-DCC mapping

Companion `edgeai-tiovx-modules` PR:

https://github.com/ereennk/edgeai-tiovx-modules/pull/2

Provides:

```text
SENSOR_SONY_IMX230_PIVARIETY -> DCC ID 230
```

This PR is maintained as a companion review PR against the corresponding GitHub source base.

### IMX230 DCC source profile

DCC repository:

https://github.com/ereennk/imx230-dcc-profile

Validated revision:

```text
ce7dc61
```

Exact revision:

https://github.com/ereennk/imx230-dcc-profile/commit/ce7dc61

Generated DCC binaries are intentionally not stored in this repository.

## Runtime prerequisites

The kernel driver, Device Tree overlay, TIOVX support, GStreamer plugin support and IMX230 DCC profile must be installed before starting this example.

By default `run.sh` loads:

```text
/opt/t3-edgeai-env
```

A different environment file can be supplied with:

```bash
T3_EDGEAI_ENV=/path/to/environment ./run.sh
```

## System packages

The application uses system-provided GObject, GStreamer, OpenCV and NumPy bindings.

On an Ubuntu-based T3 Gemstone image, the required packages include:

```bash
sudo apt update
sudo apt install \
    python3 \
    python3-venv \
    python3-gi \
    python3-gst-1.0 \
    python3-opencv \
    python3-numpy \
    gstreamer1.0-tools \
    v4l-utils
```

The target image may already contain some or all of these packages.

The following commands must be available:

```bash
python3
gst-launch-1.0
media-ctl
v4l2-ctl
```

## Camera device verification

On the validated T3 Gemstone O1 system the camera is exposed through:

```text
/dev/media0
/dev/video2
/dev/v4l-subdev2
```

Device numbering may differ if other media devices are present.

Check the media graph with:

```bash
media-ctl -p
```

Check available V4L2 devices with:

```bash
v4l2-ctl --list-devices
```

Expected sensor format:

```text
SRGGB10_1X10/1920x1080
```

Expected capture format:

```text
RG10
1920x1080
```

## Generate the IMX230 DCC files

Clone the DCC source repository and checkout the validated revision:

```bash
git clone https://github.com/ereennk/imx230-dcc-profile.git
cd imx230-dcc-profile
git checkout ce7dc61
```

The TI DCC host tools are 32-bit x86 Linux executables. Generate the
DCC files on an x86 Linux host, not directly on the ARM64 Gemstone board.

Download the pinned TI DCC tools:

```bash
./scripts/download-ti-dcc-tools.sh \
    REL.IMAGING.11.00.00.00 \
    /tmp/imx230-ti-tools
```

Generate and verify the DCC outputs:

```bash
DCC_TOOL_PATH=/tmp/imx230-ti-tools ./build.sh
./verify.sh
```

The runtime requires:

```text
dcc_viss.bin
dcc_2a.bin
```

Install the generated DCC binaries into the default runtime directory:

```bash
sudo mkdir -p /opt/imaging/imx230/linear

sudo install -m 0644 \
    dcc_bins/dcc_viss.bin \
    /opt/imaging/imx230/linear/dcc_viss.bin

sudo install -m 0644 \
    dcc_bins/dcc_2a.bin \
    /opt/imaging/imx230/linear/dcc_2a.bin
```

Verify the installation:

```bash
ls -lh \
    /opt/imaging/imx230/linear/dcc_viss.bin \
    /opt/imaging/imx230/linear/dcc_2a.bin
```

The DCC repository contains the source XML/LUT material and generation workflow. Generated DCC binaries and generated headers remain build artifacts and are not committed to the integration repositories.

## Python environment

Enter the example directory:

```bash
cd camera/imx230_pivariety_tuner
```

Create a virtual environment with access to system GObject, OpenCV and NumPy packages:

```bash
python3 -m venv --system-site-packages venv
venv/bin/pip install -r requirements.txt
```

Python-only requirements:

```text
fastapi
uvicorn
```

GObject, GStreamer, OpenCV and NumPy are expected to come from the system environment.

## Optional initial settings

A validated example profile is provided in:

```text
settings.example.json
```

To use it as the initial persistent profile:

```bash
cp settings.example.json settings.json
```

## Run

Start the application from the example directory:

```bash
./run.sh
```

Then open:

```text
http://BOARD_IP:8000
```

For local access on the board:

```text
http://127.0.0.1:8000
```

## Custom GStreamer, TIOVX and DCC locations

```bash
IMX230_GST_PLUGIN_DIR=/path/to/gst/plugins \
IMX230_TIOVX_LIB_DIR=/path/to/tiovx/lib \
IMX230_DCC_DIR=/path/to/imx230/dcc \
./run.sh
```

## Device overrides

```bash
IMX230_MEDIA_DEVICE=/dev/media0 \
IMX230_VIDEO_DEVICE=/dev/video2 \
IMX230_SENSOR_DEVICE=/dev/v4l-subdev2 \
./run.sh
```

## Optional environment variables

- `IMX230_DCC_DIR`
- `IMX230_GST_PLUGIN_DIR`
- `IMX230_TIOVX_LIB_DIR`
- `IMX230_MEDIA_DEVICE`
- `IMX230_VIDEO_DEVICE`
- `IMX230_SENSOR_DEVICE`
- `IMX230_SETTINGS_FILE`
- `IMX230_SNAPSHOT_DIR`
- `IMX230_HOST`
- `IMX230_PORT`
- `IMX230_PYTHON`
- `IMX230_GST_REGISTRY`
- `T3_EDGEAI_ENV`

Defaults used by `run.sh` include:

```text
T3_EDGEAI_ENV=/opt/t3-edgeai-env
IMX230_DCC_DIR=/opt/imaging/imx230/linear
GST registry=/tmp/gst-registry-imx230-tuner.bin
Python=camera/imx230_pivariety_tuner/venv/bin/python
```

If the virtual-environment Python interpreter is unavailable, `run.sh` falls back to system `python3`.

## Features

- Live browser preview
- Exposure control
- Analogue gain control
- Focus control
- Software automatic exposure
- Contrast-based autofocus
- Neutral-card measurement
- White-balance recommendations
- Gamma control
- Contrast control
- Saturation control
- Snapshot capture
- Persistent runtime settings

## Expected runtime path

```text
IMX230 sensor
    |
    | SRGGB10_1X10 / 1920x1080
    v
V4L2 capture
    |
    | RG10
    v
GStreamer
    |
    | video/x-bayer,format=rggb10
    v
tiovxisp
    |
    | sensor-name=SENSOR_SONY_IMX230_PIVARIETY
    | DCC ID 230
    | dcc_viss.bin
    | dcc_2a.bin
    v
processed RGB video
    |
    v
browser tuner
```

## Generated artifacts policy

Generated and runtime artifacts are intentionally excluded from this repository, including:

- virtual environments
- Python cache files
- `settings.json`
- snapshots
- JPEG/PNG captures
- RAW captures
- video captures
- kernel modules
- Device Tree binaries
- shared libraries
- DCC binaries

The source repositories contain the material required to reproduce the corresponding runtime components instead of storing generated binaries.

## Troubleshooting

### DCC files are missing

```bash
ls -l \
    /opt/imaging/imx230/linear/dcc_viss.bin \
    /opt/imaging/imx230/linear/dcc_2a.bin
```

Or specify another directory:

```bash
IMX230_DCC_DIR=/path/to/dcc ./run.sh
```

### Camera device numbering differs

```bash
media-ctl -p
v4l2-ctl --list-devices
```

Then override:

```text
IMX230_MEDIA_DEVICE
IMX230_VIDEO_DEVICE
IMX230_SENSOR_DEVICE
```

### Custom plugin builds are not detected

```bash
IMX230_GST_PLUGIN_DIR=/path/to/plugins \
IMX230_TIOVX_LIB_DIR=/path/to/libs \
./run.sh
```

`run.sh` adds these locations to `GST_PLUGIN_PATH` and `LD_LIBRARY_PATH`.

## Source-only integration

No prebuilt IMX230 `.ko`, `.so`, `.dtbo`, DCC `.bin`, RAW image or captured image is required from this repository.

The intended integration model is:

```text
source
  -> build/generate
  -> install
  -> verify
  -> run
```

This keeps the IMX230 integration reviewable and reproducible across the companion repositories.
