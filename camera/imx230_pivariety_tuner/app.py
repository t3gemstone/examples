#!/usr/bin/env python3

from __future__ import annotations

import atexit
from contextlib import asynccontextmanager
import json
import os
import pwd
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

import cv2
import gi
import numpy as np
import uvicorn
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

gi.require_version("Gst", "1.0")
from gi.repository import Gst


APP_DIR = Path(__file__).resolve().parent

PROFILE_FILE = Path(
    os.environ.get("IMX230_SETTINGS_FILE", APP_DIR / "settings.json")
)
SNAPSHOT_DIR = Path(
    os.environ.get("IMX230_SNAPSHOT_DIR", APP_DIR / "snapshots")
)

MEDIA_DEVICE = os.environ.get("IMX230_MEDIA_DEVICE", "/dev/media0")
VIDEO_DEVICE = os.environ.get("IMX230_VIDEO_DEVICE", "/dev/video2")
SENSOR_DEVICE = os.environ.get("IMX230_SENSOR_DEVICE", "/dev/v4l-subdev2")

DCC_DIR = Path(
    os.environ.get("IMX230_DCC_DIR", "/opt/imaging/imx230/linear")
)
DCC_VISS = DCC_DIR / "dcc_viss.bin"
DCC_2A = DCC_DIR / "dcc_2a.bin"

PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 360
STREAM_FPS = 8.0

# Center region used for measurements in the live preview.
ROI_WIDTH_RATIO = 0.34
ROI_HEIGHT_RATIO = 0.40

# Software automatic exposure controller.
# Sensor gain is not adjusted automatically in this version; keeping it at 100 is recommended.
DEFAULT_AE_MODE = "auto"
AE_MODES = {"auto", "manual", "locked"}
AE_INTERVAL_SECONDS = 0.70
AE_MIN_EXPOSURE = 500
AE_MAX_EXPOSURE = 20000

# Single-pass contrast-based autofocus settings.
# Perform coarse and fine scans over the center ROI.
AF_COARSE_STEP = 100
AF_FINE_RADIUS = 100
AF_FINE_STEP = 10
AF_SETTLE_SECONDS = 0.16
AF_SAMPLE_COUNT = 3
AF_SAMPLE_INTERVAL = 0.05
AF_LOW_TEXTURE_STD = 6.0

DEFAULT_SETTINGS: dict[str, Any] = {
    "exposure": 13810,
    "gain": 100,
    "focus": 121,
    "red_gain": 1.00,
    "green_gain": 0.98,
    "blue_gain": 0.98,
    "gamma": 1.50,
    "contrast": 1.06,
    "saturation": 1.25,
}

NEUTRAL_SETTINGS: dict[str, Any] = {
    "exposure": 13810,
    "gain": 100,
    "focus": 121,
    "red_gain": 1.00,
    "green_gain": 1.00,
    "blue_gain": 1.00,
    "gamma": 1.00,
    "contrast": 1.00,
    "saturation": 1.00,
}

LIMITS: dict[str, tuple[float, float]] = {
    "exposure": (20, 65478),
    "gain": (100, 800),
    "focus": (0, 1000),
    "red_gain": (0.50, 1.50),
    "green_gain": (0.50, 1.50),
    "blue_gain": (0.50, 1.50),
    "gamma": (0.50, 2.50),
    "contrast": (0.50, 1.80),
    "saturation": (0.00, 2.00),
}


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), flush=True)
    result = subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.stdout:
        print(result.stdout, end="")
    return result


def clamp(name: str, value: float | int) -> float | int:
    lower, upper = LIMITS[name]
    bounded = max(lower, min(upper, float(value)))

    if name in {"exposure", "gain", "focus"}:
        return int(round(bounded))

    return round(bounded, 2)


class CameraController:
    def __init__(self) -> None:
        self.settings_lock = threading.RLock()
        self.frame_lock = threading.Lock()
        self.sensor_lock = threading.Lock()
        self.measurement_lock = threading.Lock()
        self.autofocus_lock = threading.Lock()
        self.autofocus_state_lock = threading.Lock()

        self.settings, self.ae_mode = self._load_profile()
        self.latest_frame: np.ndarray | None = None
        self.pipeline: Gst.Pipeline | None = None
        self.running = False
        self.last_error = ""
        self.bus_thread: threading.Thread | None = None
        self.ae_thread: threading.Thread | None = None
        self.autofocus_thread: threading.Thread | None = None
        self.autofocus_cancel = threading.Event()

        self.autofocus_state: dict[str, Any] = {
            "running": False,
            "phase": "idle",
            "progress": 0,
            "current_focus": int(self.settings["focus"]),
            "best_focus": int(self.settings["focus"]),
            "best_score": 0.0,
            "texture_std": 0.0,
            "message": "Autofocus ready.",
        }

        self.ae_metrics: dict[str, float] = {
            "raw_clipped_percent": 0.0,
            "display_p50": 0.0,
            "display_p75": 0.0,
            "display_p90": 0.0,
        }
        self.ae_last_action = "Waiting for the initial value."

        self.last_measurement: dict[str, Any] | None = None
        self.undo_settings: dict[str, Any] | None = None

    def _load_profile(self) -> tuple[dict[str, Any], str]:
        settings = dict(DEFAULT_SETTINGS)
        ae_mode = DEFAULT_AE_MODE

        if PROFILE_FILE.exists():
            try:
                loaded = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    for name in settings:
                        if name in loaded:
                            settings[name] = clamp(name, loaded[name])

                    loaded_mode = str(loaded.get("ae_mode", DEFAULT_AE_MODE))
                    if loaded_mode in AE_MODES:
                        ae_mode = loaded_mode
            except (OSError, ValueError, TypeError) as exc:
                print(f"Profile could not be read; default values will be used: {exc}")

        return settings, ae_mode

    def get_settings(self) -> dict[str, Any]:
        with self.settings_lock:
            result: dict[str, Any] = dict(self.settings)
            result["ae_mode"] = self.ae_mode
            return result

    @staticmethod
    def roi_bounds(width: int, height: int) -> tuple[int, int, int, int]:
        roi_width = max(40, int(width * ROI_WIDTH_RATIO))
        roi_height = max(40, int(height * ROI_HEIGHT_RATIO))

        x1 = (width - roi_width) // 2
        y1 = (height - roi_height) // 2
        x2 = x1 + roi_width
        y2 = y1 + roi_height

        return x1, y1, x2, y2

    def configure_media(self) -> None:
        required_paths = [
            MEDIA_DEVICE,
            VIDEO_DEVICE,
            SENSOR_DEVICE,
            DCC_VISS,
            DCC_2A,
        ]

        missing = [path for path in required_paths if not Path(path).exists()]
        if missing:
            raise RuntimeError("Missing file or device: " + ", ".join(missing))

        entities = [
            '"arducam-pivariety 5-000c":0',
            '"cdns_csi2rx.30101000.csi-bridge":0',
            '"cdns_csi2rx.30101000.csi-bridge":1',
            '"30102000.ticsi2rx":0',
            '"30102000.ticsi2rx":1',
        ]

        for entity in entities:
            run_command([
                "media-ctl",
                "-d",
                MEDIA_DEVICE,
                "--set-v4l2",
                f"{entity} [fmt:SRGGB10_1X10/1920x1080 field:none]",
            ])

        run_command([
            "v4l2-ctl",
            "-d",
            VIDEO_DEVICE,
            "--set-fmt-video=width=1920,height=1080,pixelformat=RG10",
        ])

        current = self.get_settings()
        self.set_sensor_controls(
            exposure=int(current["exposure"]),
            gain=int(current["gain"]),
            focus=int(current["focus"]),
        )

    def set_sensor_controls(
        self,
        *,
        exposure: int | None = None,
        gain: int | None = None,
        focus: int | None = None,
    ) -> None:
        controls: list[str] = []

        if exposure is not None:
            controls.append(f"exposure={int(clamp('exposure', exposure))}")
        if gain is not None:
            controls.append(f"analogue_gain={int(clamp('gain', gain))}")
        if focus is not None:
            controls.append(f"focus_absolute={int(clamp('focus', focus))}")

        if not controls:
            return

        with self.sensor_lock:
            run_command([
                "v4l2-ctl",
                "-d",
                SENSOR_DEVICE,
                "--set-ctrl",
                ",".join(controls),
            ])

    def start(self) -> None:
        if self.running:
            return

        Gst.init(None)
        self.configure_media()

        pipeline_text = f"""
            v4l2src
                device={VIDEO_DEVICE}
                io-mode=dmabuf-import
            ! video/x-bayer,format=rggb10,width=1920,height=1080
            ! tiovxisp
                sensor-name=SENSOR_SONY_IMX230_PIVARIETY
                dcc-isp-file={DCC_VISS}
                sink_0::dcc-2a-file={DCC_2A}
                sink_0::device={SENSOR_DEVICE}
                sink_0::ae-mode=2
                sink_0::awb-mode=2
                format-msb=9
            ! video/x-raw,format=NV12,width=1920,height=1080
            ! queue max-size-buffers=2 leaky=downstream
            ! videoscale
            ! video/x-raw,width={PREVIEW_WIDTH},height={PREVIEW_HEIGHT}
            ! videoconvert
            ! video/x-raw,format=BGR
            ! appsink
                name=preview_sink
                emit-signals=true
                max-buffers=1
                drop=true
                sync=false
        """

        parsed = Gst.parse_launch(pipeline_text)
        if not isinstance(parsed, Gst.Pipeline):
            raise RuntimeError("Failed to create the GStreamer pipeline.")

        self.pipeline = parsed
        sink = self.pipeline.get_by_name("preview_sink")

        if sink is None:
            raise RuntimeError("GStreamer appsink was not found.")

        sink.connect("new-sample", self._on_sample)

        state_result = self.pipeline.set_state(Gst.State.PLAYING)
        if state_result == Gst.StateChangeReturn.FAILURE:
            self.pipeline.set_state(Gst.State.NULL)
            raise RuntimeError("Failed to start the GStreamer pipeline.")

        self.running = True
        self.last_error = ""

        self.bus_thread = threading.Thread(
            target=self._monitor_bus,
            name="gstreamer-bus",
            daemon=True,
        )
        self.bus_thread.start()

        self.ae_thread = threading.Thread(
            target=self._auto_exposure_loop,
            name="imx230-auto-exposure",
            daemon=True,
        )
        self.ae_thread.start()

        print("IMX230 live pipeline started successfully.", flush=True)

    def stop(self) -> None:
        self.autofocus_cancel.set()
        self.running = False

        if self.pipeline is not None:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

    def _compute_ae_metrics(self) -> dict[str, float] | None:
        raw = self.raw_frame()
        display = self.adjusted_frame(draw_roi=False)

        if raw is None or display is None:
            return None

        raw_maximum = np.max(raw, axis=2)
        raw_clipped_percent = float(
            np.mean(raw_maximum >= 250) * 100.0
        )

        display_luma = cv2.cvtColor(display, cv2.COLOR_BGR2GRAY)

        return {
            "raw_clipped_percent": raw_clipped_percent,
            "display_p50": float(np.percentile(display_luma, 50)),
            "display_p75": float(np.percentile(display_luma, 75)),
            "display_p90": float(np.percentile(display_luma, 90)),
        }

    def _auto_exposure_loop(self) -> None:
        while self.running:
            time.sleep(AE_INTERVAL_SECONDS)

            with self.settings_lock:
                mode = self.ae_mode
                current_exposure = int(self.settings["exposure"])

            if mode != "auto":
                continue

            metrics = self._compute_ae_metrics()
            if metrics is None:
                continue

            with self.settings_lock:
                self.ae_metrics = dict(metrics)

            clipped = metrics["raw_clipped_percent"]
            p75 = metrics["display_p75"]
            p90 = metrics["display_p90"]

            factor = 1.0
            reason = "Exposure is balanced; keeping the current value."

            # Respond quickly when returning to a bright scene.
            if clipped >= 10.0:
                factor = 0.60
                reason = "Severe clipping detected; exposure was reduced quickly."
            elif clipped >= 5.0:
                factor = 0.72
                reason = "High clipping detected; exposure was reduced."
            elif clipped >= 2.0:
                factor = 0.84
                reason = "Too many bright areas; exposure was reduced."
            elif clipped >= 1.0:
                factor = 0.92
                reason = "Mild clipping detected; exposure was reduced slightly."

            # Increase exposure gradually in dark scenes.
            elif p75 < 55.0:
                factor = 1.20
                reason = "Scene is very dark; exposure was increased."
            elif p75 < 75.0:
                factor = 1.12
                reason = "Scene is dark; exposure was increased."
            elif p75 < 90.0:
                factor = 1.06
                reason = "Midtones are low; exposure was increased slightly."

            # Apply a gentle reduction in bright scenes that are not fully clipped.
            elif p90 > 230.0 and clipped > 0.40:
                factor = 0.95
                reason = "Highlights are near the limit; exposure was reduced slightly."

            target_exposure = int(round(current_exposure * factor))
            target_exposure = max(
                AE_MIN_EXPOSURE,
                min(AE_MAX_EXPOSURE, target_exposure),
            )

            # Reduce oscillation by ignoring very small adjustments.
            if abs(target_exposure - current_exposure) < 80:
                with self.settings_lock:
                    self.ae_last_action = reason
                continue

            try:
                self.update_settings({"exposure": target_exposure})
                with self.settings_lock:
                    self.ae_last_action = (
                        f"{reason} {current_exposure} → {target_exposure}"
                    )
            except subprocess.CalledProcessError as exc:
                with self.settings_lock:
                    self.ae_last_action = f"AE control error: {exc}"

    def _monitor_bus(self) -> None:
        if self.pipeline is None:
            return

        bus = self.pipeline.get_bus()
        watched = Gst.MessageType.ERROR | Gst.MessageType.EOS

        while self.running:
            message = bus.timed_pop_filtered(500 * Gst.MSECOND, watched)
            if message is None:
                continue

            if message.type == Gst.MessageType.ERROR:
                error, debug = message.parse_error()
                self.last_error = str(error)
                print(f"GStreamer error: {error}", flush=True)
                if debug:
                    print(debug, flush=True)
                self.running = False
                break

            if message.type == Gst.MessageType.EOS:
                self.last_error = "Camera stream ended."
                self.running = False
                break

    def _on_sample(self, sink: Any) -> Gst.FlowReturn:
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.ERROR

        caps = sample.get_caps()
        structure = caps.get_structure(0)
        width = int(structure.get_value("width"))
        height = int(structure.get_value("height"))

        buffer = sample.get_buffer()
        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            return Gst.FlowReturn.ERROR

        try:
            expected = width * height * 3
            pixels = np.frombuffer(map_info.data, dtype=np.uint8)

            if pixels.size < expected:
                self.last_error = (
                    f"Incomplete image buffer: expected {expected}, received {pixels.size}"
                )
                return Gst.FlowReturn.ERROR

            frame = pixels[:expected].reshape((height, width, 3)).copy()

            with self.frame_lock:
                self.latest_frame = frame

            return Gst.FlowReturn.OK
        finally:
            buffer.unmap(map_info)

    def raw_frame(self) -> np.ndarray | None:
        with self.frame_lock:
            if self.latest_frame is None:
                return None
            return self.latest_frame.copy()

    def adjusted_frame(self, *, draw_roi: bool = False) -> np.ndarray | None:
        frame = self.raw_frame()
        if frame is None:
            return None

        settings = self.get_settings()
        result = frame.astype(np.float32)

        # OpenCV uses BGR channel ordering.
        result[:, :, 0] *= float(settings["blue_gain"])
        result[:, :, 1] *= float(settings["green_gain"])
        result[:, :, 2] *= float(settings["red_gain"])

        output = np.clip(result, 0, 255).astype(np.uint8)

        # User gamma value:
        # 1.00 = no change
        # Greater than 1.00 = brighten midtones
        # Less than 1.00 = darken midtones
        gamma = float(settings["gamma"])
        if abs(gamma - 1.0) > 0.001:
            gamma_lut = np.clip(
                ((np.arange(256, dtype=np.float32) / 255.0) ** (1.0 / gamma))
                * 255.0,
                0,
                255,
            ).astype(np.uint8)
            output = cv2.LUT(output, gamma_lut)

        # Apply contrast around middle gray (127.5).
        contrast = float(settings["contrast"])
        if abs(contrast - 1.0) > 0.001:
            contrasted = (
                (output.astype(np.float32) - 127.5) * contrast
                + 127.5
            )
            output = np.clip(contrasted, 0, 255).astype(np.uint8)

        # Saturation: linear blend between the grayscale and color images.
        # This method adjusts saturation without changing hue.
        saturation = float(settings["saturation"])
        if abs(saturation - 1.0) > 0.001:
            gray = cv2.cvtColor(output, cv2.COLOR_BGR2GRAY).astype(np.float32)
            gray3 = np.repeat(gray[:, :, None], 3, axis=2)
            saturated = (
                gray3
                + saturation
                * (output.astype(np.float32) - gray3)
            )
            output = np.clip(saturated, 0, 255).astype(np.uint8)

        if draw_roi:
            height, width = output.shape[:2]
            x1, y1, x2, y2 = self.roi_bounds(width, height)

            cv2.rectangle(output, (x1, y1), (x2, y2), (0, 220, 255), 2)
            cv2.putText(
                output,
                "Neutral card measurement area",
                (x1, max(22, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                (0, 220, 255),
                2,
                cv2.LINE_AA,
            )

        return output

    def _set_autofocus_state(self, **changes: Any) -> None:
        with self.autofocus_state_lock:
            self.autofocus_state.update(changes)

    def get_autofocus_status(self) -> dict[str, Any]:
        with self.autofocus_state_lock:
            return dict(self.autofocus_state)

    def _set_focus_position(self, position: int) -> int:
        bounded = int(clamp("focus", position))
        self.set_sensor_controls(focus=bounded)

        with self.settings_lock:
            self.settings["focus"] = bounded

        self._set_autofocus_state(current_focus=bounded)
        return bounded

    def _focus_score_once(self) -> tuple[float, float]:
        frame = self.raw_frame()
        if frame is None:
            raise RuntimeError("Could not acquire a camera frame for autofocus.")

        height, width = frame.shape[:2]
        x1, y1, x2, y2 = self.roi_bounds(width, height)
        roi = frame[y1:y2, x1:x2]

        if roi.size == 0:
            raise RuntimeError("Autofocus ROI is empty.")

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        texture_std = float(np.std(gray))

        # A light blur reduces artificial sharpness scores caused by sensor noise.
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = grad_x * grad_x + grad_y * grad_y

        # Use the strongest quartile of edges. A flat background does not
        # unnecessarily lower the score, while noise is suppressed by the blur.
        threshold = float(np.percentile(magnitude, 75))
        strong_edges = magnitude[magnitude >= threshold]

        if strong_edges.size == 0:
            return 0.0, texture_std

        score = float(np.mean(strong_edges))
        return score, texture_std

    def _sample_focus_score(self) -> tuple[float, float]:
        scores: list[float] = []
        textures: list[float] = []

        for _ in range(AF_SAMPLE_COUNT):
            if self.autofocus_cancel.is_set():
                raise RuntimeError("Autofocus iptal edildi.")

            time.sleep(AF_SAMPLE_INTERVAL)
            score, texture = self._focus_score_once()
            scores.append(score)
            textures.append(texture)

        return float(np.median(scores)), float(np.median(textures))

    def start_autofocus(self) -> dict[str, Any]:
        if not self.running:
            raise RuntimeError("Camera is not running.")

        if not self.autofocus_lock.acquire(blocking=False):
            raise RuntimeError("Autofocus is already running.")

        self.autofocus_cancel.clear()
        self._set_autofocus_state(
            running=True,
            phase="starting",
            progress=0,
            current_focus=int(self.get_settings()["focus"]),
            best_focus=int(self.get_settings()["focus"]),
            best_score=0.0,
            texture_std=0.0,
            message="Locking exposure and starting autofocus.",
        )

        self.autofocus_thread = threading.Thread(
            target=self._autofocus_worker,
            name="imx230-single-autofocus",
            daemon=True,
        )
        self.autofocus_thread.start()

        return self.get_autofocus_status()

    def _autofocus_worker(self) -> None:
        previous_settings = self.get_settings()
        previous_mode = str(previous_settings["ae_mode"])
        previous_focus = int(previous_settings["focus"])

        try:
            # Exposure and gain must remain unchanged during AF.
            self.update_settings({"ae_mode": "locked"})
            time.sleep(0.35)

            focus_min = int(LIMITS["focus"][0])
            focus_max = int(LIMITS["focus"][1])

            coarse_positions = list(
                range(focus_min, focus_max + 1, AF_COARSE_STEP)
            )
            if coarse_positions[-1] != focus_max:
                coarse_positions.append(focus_max)

            best_focus = previous_focus
            best_score = -1.0
            best_texture = 0.0

            for index, position in enumerate(coarse_positions, start=1):
                if self.autofocus_cancel.is_set():
                    raise RuntimeError("Autofocus iptal edildi.")

                applied = self._set_focus_position(position)
                time.sleep(AF_SETTLE_SECONDS)
                score, texture = self._sample_focus_score()

                if score > best_score:
                    best_score = score
                    best_focus = applied
                    best_texture = texture

                self._set_autofocus_state(
                    phase="coarse",
                    progress=int(index / len(coarse_positions) * 55),
                    current_focus=applied,
                    best_focus=best_focus,
                    best_score=round(best_score, 2),
                    texture_std=round(best_texture, 2),
                    message=(
                        f"Kaba tarama: focus={applied}, "
                        f"puan={score:.1f}"
                    ),
                )

            fine_start = max(focus_min, best_focus - AF_FINE_RADIUS)
            fine_end = min(focus_max, best_focus + AF_FINE_RADIUS)
            fine_positions = list(
                range(fine_start, fine_end + 1, AF_FINE_STEP)
            )

            if fine_positions[-1] != fine_end:
                fine_positions.append(fine_end)

            for index, position in enumerate(fine_positions, start=1):
                if self.autofocus_cancel.is_set():
                    raise RuntimeError("Autofocus iptal edildi.")

                applied = self._set_focus_position(position)
                time.sleep(AF_SETTLE_SECONDS)
                score, texture = self._sample_focus_score()

                if score > best_score:
                    best_score = score
                    best_focus = applied
                    best_texture = texture

                self._set_autofocus_state(
                    phase="fine",
                    progress=55 + int(index / len(fine_positions) * 44),
                    current_focus=applied,
                    best_focus=best_focus,
                    best_score=round(best_score, 2),
                    texture_std=round(best_texture, 2),
                    message=(
                        f"Fine scan: focus={applied}, "
                        f"puan={score:.1f}"
                    ),
                )

            self._set_focus_position(best_focus)
            time.sleep(AF_SETTLE_SECONDS)

            if best_texture < AF_LOW_TEXTURE_STD:
                message = (
                    f"AF completed: focus={best_focus}. "
                    "ROI contains little detail; verify the result visually."
                )
            else:
                message = (
                    f"AF completed: best focus={best_focus}, "
                    f"sharpness score={best_score:.1f}."
                )

            self._set_autofocus_state(
                running=False,
                phase="completed",
                progress=100,
                current_focus=best_focus,
                best_focus=best_focus,
                best_score=round(best_score, 2),
                texture_std=round(best_texture, 2),
                message=message,
            )

        except Exception as exc:
            try:
                if self.running:
                    self._set_focus_position(previous_focus)
            except Exception:
                pass

            self._set_autofocus_state(
                running=False,
                phase="error",
                progress=0,
                current_focus=previous_focus,
                best_focus=previous_focus,
                message=f"Autofocus failed: {exc}",
            )

        finally:
            try:
                if self.running and previous_mode in AE_MODES:
                    self.update_settings({"ae_mode": previous_mode})
            except Exception as exc:
                self._set_autofocus_state(
                    message=(
                        self.get_autofocus_status().get("message", "")
                        + f" Exposure mode could not be restored: {exc}"
                    )
                )

            self.autofocus_lock.release()

    def update_settings(self, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = set(DEFAULT_SETTINGS) | {"ae_mode"}
        unknown = set(changes) - allowed

        if unknown:
            raise ValueError("Bilinmeyen ayarlar: " + ", ".join(sorted(unknown)))

        sensor_changes: dict[str, int] = {}

        with self.settings_lock:
            if "ae_mode" in changes:
                requested_mode = str(changes["ae_mode"])
                if requested_mode not in AE_MODES:
                    raise ValueError(
                        "AE mode must be auto, manual, or locked."
                    )
                self.ae_mode = requested_mode
                self.ae_last_action = {
                    "auto": "Otomatik exposure etkin.",
                    "manual": "Manuel exposure etkin.",
                    "locked": "Mevcut exposure kilitlendi.",
                }[requested_mode]

            for name, raw_value in changes.items():
                if name == "ae_mode":
                    continue

                value = clamp(name, raw_value)
                self.settings[name] = value

                if name in {"exposure", "gain", "focus"}:
                    sensor_changes[name] = int(value)

        if sensor_changes:
            self.set_sensor_controls(
                exposure=sensor_changes.get("exposure"),
                gain=sensor_changes.get("gain"),
                focus=sensor_changes.get("focus"),
            )

        return self.get_settings()

    def save_profile(self) -> None:
        PROFILE_FILE.write_text(
            json.dumps(self.get_settings(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def reset(self, neutral: bool = False) -> dict[str, Any]:
        target: dict[str, Any] = dict(
            NEUTRAL_SETTINGS if neutral else DEFAULT_SETTINGS
        )
        target["ae_mode"] = "manual" if neutral else DEFAULT_AE_MODE
        return self.update_settings(target)

    def stats(self) -> dict[str, Any]:
        frame = self.adjusted_frame()
        if frame is None:
            return {
                "ready": False,
                "running": self.running,
                "error": self.last_error,
            }

        b_mean, g_mean, r_mean = np.mean(frame, axis=(0, 1))
        maximum = np.max(frame, axis=2)
        minimum = np.min(frame, axis=2)

        clipped = float(np.mean(maximum >= 250) * 100.0)
        dark = float(np.mean(maximum <= 5) * 100.0)

        return {
            "ready": True,
            "running": self.running,
            "error": self.last_error,
            "mean_r": round(float(r_mean), 1),
            "mean_g": round(float(g_mean), 1),
            "mean_b": round(float(b_mean), 1),
            "clipped_percent": round(clipped, 2),
            "dark_percent": round(dark, 2),
            "ae_mode": self.ae_mode,
            "ae_raw_clipped_percent": round(
                float(self.ae_metrics["raw_clipped_percent"]),
                2,
            ),
            "ae_p50": round(float(self.ae_metrics["display_p50"]), 1),
            "ae_p75": round(float(self.ae_metrics["display_p75"]), 1),
            "ae_p90": round(float(self.ae_metrics["display_p90"]), 1),
            "ae_last_action": self.ae_last_action,
            "current_focus": int(self.get_settings()["focus"]),
            "autofocus": self.get_autofocus_status(),
        }

    def measure_neutral(self, target_kind: str) -> dict[str, Any]:
        frame = self.raw_frame()
        if frame is None:
            raise RuntimeError("No camera frame has been acquired yet.")

        if target_kind not in {"gray", "white"}:
            raise ValueError("Target type must be gray or white.")

        height, width = frame.shape[:2]
        x1, y1, x2, y2 = self.roi_bounds(width, height)
        roi = frame[y1:y2, x1:x2]

        blue = roi[:, :, 0].astype(np.float32)
        green = roi[:, :, 1].astype(np.float32)
        red = roi[:, :, 2].astype(np.float32)

        maximum = np.maximum(np.maximum(red, green), blue)
        minimum = np.minimum(np.minimum(red, green), blue)

        clipped_mask = maximum >= 250
        dark_mask = maximum <= 10
        valid_mask = (~clipped_mask) & (~dark_mask)

        valid_count = int(np.count_nonzero(valid_mask))
        total_count = int(valid_mask.size)

        if valid_count < max(500, int(total_count * 0.25)):
            raise RuntimeError(
                "There are not enough valid pixels in the measurement area. "
                "The card may be too dark or clipped."
            )

        r_median = float(np.median(red[valid_mask]))
        g_median = float(np.median(green[valid_mask]))
        b_median = float(np.median(blue[valid_mask]))

        if min(r_median, g_median, b_median) < 1.0:
            raise RuntimeError("Channel measurement is not reliable.")

        # Treat the lowest channel as 1.00 and reduce only the higher channels.
        # This prevents software white balance from introducing additional highlight clipping.
        neutral_level = min(r_median, g_median, b_median)

        red_gain = float(clamp("red_gain", neutral_level / r_median))
        green_gain = float(clamp("green_gain", neutral_level / g_median))
        blue_gain = float(clamp("blue_gain", neutral_level / b_median))

        luminance = (
            0.2126 * red
            + 0.7152 * green
            + 0.0722 * blue
        )
        luma_median = float(np.median(luminance[valid_mask]))

        clipped_percent = float(np.mean(clipped_mask) * 100.0)
        dark_percent = float(np.mean(dark_mask) * 100.0)
        valid_percent = float(valid_count / total_count * 100.0)

        target_luma = 128.0 if target_kind == "gray" else 190.0
        current = self.get_settings()
        current_exposure = int(current["exposure"])

        if clipped_percent > 1.0:
            exposure_factor = min(0.80, target_luma / max(luma_median, 1.0))
        else:
            exposure_factor = target_luma / max(luma_median, 1.0)

        # Prevent excessive adjustment from a single measurement.
        exposure_factor = max(0.60, min(1.60, exposure_factor))
        recommended_exposure = int(
            clamp("exposure", round(current_exposure * exposure_factor))
        )

        channel_values = {
            "red": r_median,
            "green": g_median,
            "mavi": b_median,
        }
        highest_name = max(channel_values, key=channel_values.get)
        lowest_name = min(channel_values, key=channel_values.get)
        channel_ratio = max(channel_values.values()) / min(channel_values.values())

        if channel_ratio <= 1.05:
            color_diagnosis = "Neutral channels are close to each other."
        else:
            color_diagnosis = (
                f"{highest_name.capitalize()} channel is high, "
                f"{lowest_name} channel appears low."
            )

        lower_ok = target_luma * 0.82
        upper_ok = target_luma * 1.12

        if clipped_percent > 1.0:
            exposure_diagnosis = (
                f"{clipped_percent:.2f}% of the measurement area is clipped. "
                "Exposure should be reduced."
            )
        elif luma_median < lower_ok:
            exposure_diagnosis = (
                f"Card is dark (median {luma_median:.1f}). "
                "Exposure can be increased."
            )
        elif luma_median > upper_ok:
            exposure_diagnosis = (
                f"Card is too bright (median {luma_median:.1f}). "
                "Exposure can be reduced."
            )
        else:
            exposure_diagnosis = (
                f"Card brightness is within the acceptable range (median {luma_median:.1f})."
            )

        warning = ""
        if channel_ratio > 1.80:
            warning = (
                "The difference between channels is too large. Make sure the measurement area contains only "
                "a gray/white card and is illuminated by a single consistent light source."
            )

        measurement = {
            "target_kind": target_kind,
            "roi": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            "median_r": round(r_median, 2),
            "median_g": round(g_median, 2),
            "median_b": round(b_median, 2),
            "median_luma": round(luma_median, 2),
            "clipped_percent": round(clipped_percent, 2),
            "dark_percent": round(dark_percent, 2),
            "valid_percent": round(valid_percent, 2),
            "color_diagnosis": color_diagnosis,
            "exposure_diagnosis": exposure_diagnosis,
            "warning": warning,
            "recommended": {
                "red_gain": red_gain,
                "green_gain": green_gain,
                "blue_gain": blue_gain,
                "exposure": recommended_exposure,
            },
        }

        with self.measurement_lock:
            self.last_measurement = measurement

        return measurement

    def apply_recommendation(
        self,
        *,
        apply_wb: bool,
        apply_exposure: bool,
    ) -> dict[str, Any]:
        with self.measurement_lock:
            measurement = self.last_measurement

        if measurement is None:
            raise RuntimeError("Perform a neutral-card measurement first.")

        recommended = measurement["recommended"]
        changes: dict[str, Any] = {}

        if apply_wb:
            changes.update({
                "red_gain": recommended["red_gain"],
                "green_gain": recommended["green_gain"],
                "blue_gain": recommended["blue_gain"],
            })

        if apply_exposure:
            changes["exposure"] = recommended["exposure"]

        if not changes:
            raise ValueError("No recommendation was selected to apply.")

        self.undo_settings = self.get_settings()
        return self.update_settings(changes)

    def undo_last(self) -> dict[str, Any]:
        if self.undo_settings is None:
            raise RuntimeError("There is no recommendation to undo.")

        target = self.undo_settings
        self.undo_settings = None
        return self.update_settings(target)

    def snapshot(self) -> Path:
        frame = self.adjusted_frame(draw_roi=False)
        if frame is None:
            raise RuntimeError("No camera frame has been acquired yet.")

        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = SNAPSHOT_DIR / f"imx230-{timestamp}.jpg"

        if not cv2.imwrite(str(output), frame):
            raise RuntimeError("Failed to write the JPEG file.")

        try:
            account = pwd.getpwnam("gemstone")
            os.chown(output, account.pw_uid, account.pw_gid)
        except (KeyError, PermissionError):
            pass

        return output

    def mjpeg_stream(self) -> Iterator[bytes]:
        frame_interval = 1.0 / STREAM_FPS

        while True:
            started = time.monotonic()
            frame = self.adjusted_frame(draw_roi=True)

            if frame is None:
                frame = np.zeros(
                    (PREVIEW_HEIGHT, PREVIEW_WIDTH, 3),
                    dtype=np.uint8,
                )
                cv2.putText(
                    frame,
                    "Waiting for camera...",
                    (145, 185),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )

            ok, encoded = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), 82],
            )

            if ok:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + encoded.tobytes()
                    + b"\r\n"
                )

            elapsed = time.monotonic() - started
            time.sleep(max(0.0, frame_interval - elapsed))


camera = CameraController()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    camera.start()
    try:
        yield
    finally:
        camera.stop()


app = FastAPI(
    title="IMX230 Pivariety Tuner",
    lifespan=lifespan,
)

atexit.register(camera.stop)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return HTML_PAGE


@app.get("/video")
def video() -> StreamingResponse:
    return StreamingResponse(
        camera.mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return camera.get_settings()


@app.post("/api/settings")
def set_settings(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return camera.update_settings(payload)
    except (ValueError, TypeError, subprocess.CalledProcessError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/save")
def save_profile() -> dict[str, str]:
    camera.save_profile()
    return {"status": "saved", "path": str(PROFILE_FILE)}


@app.post("/api/reset")
def reset_profile(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    neutral = bool(payload.get("neutral", False))
    return camera.reset(neutral=neutral)


@app.post("/api/snapshot")
def snapshot() -> dict[str, str]:
    try:
        output = camera.snapshot()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"status": "saved", "path": str(output)}


@app.post("/api/autofocus")
def autofocus() -> JSONResponse:
    try:
        result = camera.start_autofocus()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return JSONResponse(result)


@app.get("/api/stats")
def stats() -> JSONResponse:
    return JSONResponse(camera.stats())


@app.post("/api/measure-neutral")
def measure_neutral(payload: dict[str, Any] = Body(default={})) -> JSONResponse:
    try:
        result = camera.measure_neutral(
            str(payload.get("target_kind", "gray"))
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(result)


@app.post("/api/apply-recommendation")
def apply_recommendation(
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    try:
        return camera.apply_recommendation(
            apply_wb=bool(payload.get("apply_wb", False)),
            apply_exposure=bool(payload.get("apply_exposure", False)),
        )
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/undo")
def undo() -> dict[str, Any]:
    try:
        return camera.undo_last()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


HTML_PAGE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IMX230 Color Tuning V8</title>
<style>
:root {
    color-scheme: dark;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body {
    margin: 0;
    background: #111318;
    color: #eef1f5;
}
header {
    padding: 16px 22px;
    border-bottom: 1px solid #30343b;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
header h1 { margin: 0; font-size: 20px; }
main {
    display: grid;
    grid-template-columns: minmax(500px, 1fr) 390px;
    gap: 18px;
    padding: 18px;
}
.panel {
    background: #191c22;
    border: 1px solid #30343b;
    border-radius: 12px;
    padding: 14px;
}
.preview {
    width: 100%;
    display: block;
    border-radius: 8px;
    background: #000;
    aspect-ratio: 16 / 9;
    object-fit: contain;
}
.stats {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 8px;
    margin-top: 12px;
}
.stat {
    padding: 9px;
    border-radius: 8px;
    background: #23272f;
    text-align: center;
}
.stat b { display: block; font-size: 16px; }
.stat small { color: #aeb6c2; }
.section-title {
    margin: 4px 0 13px;
    font-size: 16px;
}
.control { margin-bottom: 15px; }
.control-head {
    display: flex;
    justify-content: space-between;
    margin-bottom: 6px;
}
.control label { font-weight: 650; }
.value {
    font-variant-numeric: tabular-nums;
    color: #b9c5d5;
}
input[type="range"] { width: 100%; }
select {
    width: 100%;
    padding: 9px;
    border-radius: 8px;
    color: #fff;
    background: #272c34;
    border: 1px solid #414852;
}
.buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 9px;
    margin-top: 13px;
}
button {
    border: 1px solid #414852;
    border-radius: 8px;
    background: #272c34;
    color: #fff;
    padding: 10px;
    cursor: pointer;
    font-weight: 650;
}
button:hover { background: #313740; }
button.primary {
    background: #3568d4;
    border-color: #4a7ce5;
}
button.measure {
    background: #98641a;
    border-color: #bd8231;
}
hr {
    border: 0;
    border-top: 1px solid #343942;
    margin: 18px 0;
}
#measurement {
    margin-top: 13px;
    padding: 12px;
    border-radius: 9px;
    background: #22262d;
    line-height: 1.48;
    font-size: 14px;
}
.measure-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 7px;
    margin: 9px 0;
}
.measure-item {
    background: #2a2f37;
    border-radius: 7px;
    padding: 7px;
    text-align: center;
}
.measure-item b { display: block; }
.warning { color: #ffcc72; margin-top: 8px; }
.good { color: #90dfa8; }
#message {
    min-height: 22px;
    margin-top: 12px;
    color: #bec7d3;
    font-size: 14px;
    word-break: break-word;
}
.note {
    color: #aeb6c2;
    font-size: 13px;
    line-height: 1.45;
    margin-top: 12px;
}
@media (max-width: 980px) {
    main { grid-template-columns: 1fr; }
    .stats { grid-template-columns: repeat(3, 1fr); }
}
</style>
</head>
<body>
<header>
    <h1>IMX230 Live Color Tuning V8</h1>
    <span id="status">Connecting…</span>
</header>

<main>
    <section class="panel">
        <img class="preview" src="/video" alt="Live IMX230 preview">

        <div class="stats">
            <div class="stat"><b id="mean-r">–</b><small>Genel R</small></div>
            <div class="stat"><b id="mean-g">–</b><small>Genel G</small></div>
            <div class="stat"><b id="mean-b">–</b><small>Genel B</small></div>
            <div class="stat"><b id="clipped">–</b><small>Patlayan %</small></div>
            <div class="stat"><b id="dark">–</b><small>Dark %</small></div>
        </div>

        <p class="note">
            Fill the yellow frame only with a matte gray card or matte white A4 sheet.
            Avoid glare on the card and do not use two different light sources at the same time.
            Measurements are performed on the ISP image before user RGB and gamma adjustments.
            In this version, the automatic controller adjusts exposure only;
            analogue gain remains fixed at 100.
            Gamma affects midtones, contrast affects light-dark separation,
            and saturation controls color intensity.
        </p>
    </section>

    <aside class="panel">
        <div id="controls"></div>
        <div id="ae-info" class="note">
            Otomatik exposure verileri bekleniyor.
        </div>

        <hr>

        <h2 class="section-title">Neutral-card measurement</h2>

        <div class="control">
            <label for="target-kind">Measurement target</label>
            <select id="target-kind">
                <option value="gray">Neutral gray card</option>
                <option value="white">Mat beyaz A4</option>
            </select>
        </div>

        <button class="measure" id="measure" style="width:100%">
            Measure Gray/White Card
        </button>

        <div id="measurement">
            Fill the yellow frame with the card and press the measurement button.
        </div>

        <div class="buttons">
            <button class="primary" id="apply-wb">Apply WB Recommendation</button>
            <button id="apply-exposure">Apply Exposure Recommendation</button>
            <button id="apply-both">Apply Both</button>
            <button id="undo">Undo Last Recommendation</button>
        </div>

        <hr>

        <h2 class="section-title">Otomatik odak</h2>
        <div class="note">
            Place text, a cable, a card edge, or another textured target inside the yellow frame.
            Exposure and gain are temporarily locked during the autofocus scan.
        </div>
        <button class="primary" id="autofocus">
            Tek Sefer Otomatik Odakla
        </button>
        <div id="autofocus-info" class="note">
            Autofocus ready.
        </div>

        <hr>

        <div class="buttons">
            <button class="primary" id="save">Profili kaydet</button>
            <button id="snapshot">Save Snapshot</button>
            <button id="recommended">Recommended Profile</button>
            <button id="neutral">Neutralize RGB</button>
        </div>

        <div id="message"></div>
    </aside>
</main>

<script>
const controlDefinitions = [
    {key:"exposure", label:"Exposure", min:20, max:65478, step:10, digits:0},
    {key:"gain", label:"Analogue gain", min:100, max:800, step:1, digits:0},
    {key:"focus", label:"Focus", min:0, max:1000, step:1, digits:0},
    {key:"red_gain", label:"Red gain", min:0.50, max:1.50, step:0.01, digits:2},
    {key:"green_gain", label:"Green gain", min:0.50, max:1.50, step:0.01, digits:2},
    {key:"blue_gain", label:"Blue gain", min:0.50, max:1.50, step:0.01, digits:2},
    {key:"gamma", label:"Gamma / orta ton", min:0.50, max:2.50, step:0.01, digits:2},
    {key:"contrast", label:"Kontrast", min:0.50, max:1.80, step:0.01, digits:2},
    {key:"saturation", label:"Saturation", min:0.00, max:2.00, step:0.01, digits:2},
];

const controls = document.getElementById("controls");
let updateTimer = null;
let lastMeasurement = null;
let autofocusRunning = false;

function formatValue(def, value) {
    return Number(value).toFixed(def.digits);
}

function setSliderValues(settings) {
    const aeMode = document.getElementById("ae-mode");
    if (aeMode && settings.ae_mode) {
        aeMode.value = settings.ae_mode;
    }

    for (const def of controlDefinitions) {
        const slider = document.getElementById(def.key);
        const label = document.getElementById(def.key + "-value");

        if (slider && settings[def.key] !== undefined) {
            slider.value = settings[def.key];
        }
        if (label && settings[def.key] !== undefined) {
            label.textContent = formatValue(def, settings[def.key]);
        }
    }

    refreshAeControlState();
}

function refreshAeControlState() {
    const aeMode = document.getElementById("ae-mode");
    const exposure = document.getElementById("exposure");
    const focus = document.getElementById("focus");
    const autofocusButton = document.getElementById("autofocus");

    if (!aeMode || !exposure) return;

    exposure.disabled = aeMode.value !== "manual" || autofocusRunning;
    aeMode.disabled = autofocusRunning;

    if (focus) focus.disabled = autofocusRunning;
    if (autofocusButton) autofocusButton.disabled = autofocusRunning;
}

async function setAeMode(mode) {
    try {
        const response = await fetch("/api/settings", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ae_mode: mode}),
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to change AE mode.");
        }

        setSliderValues(data);
        showMessage(
            mode === "auto"
                ? "Automatic exposure is enabled. Gain remains fixed at its current value."
                : mode === "locked"
                    ? "Exposure is locked at its current value."
                    : "Manuel exposure etkin."
        );
    } catch (error) {
        showMessage(error.message);
    }
}

function buildControls(settings) {
    controls.innerHTML = `
        <h2 class="section-title">Camera Controls</h2>
        <div class="control">
            <label for="ae-mode">Exposure Mode</label>
            <select id="ae-mode">
                <option value="auto">Otomatik</option>
                <option value="manual">Manuel</option>
                <option value="locked">Kilitli</option>
            </select>
        </div>
    `;

    const aeMode = document.getElementById("ae-mode");
    aeMode.value = settings.ae_mode || "auto";
    aeMode.addEventListener("change", () => setAeMode(aeMode.value));

    for (const def of controlDefinitions) {
        const block = document.createElement("div");
        block.className = "control";
        block.innerHTML = `
            <div class="control-head">
                <label for="${def.key}">${def.label}</label>
                <span class="value" id="${def.key}-value"></span>
            </div>
            <input
                id="${def.key}"
                type="range"
                min="${def.min}"
                max="${def.max}"
                step="${def.step}"
                value="${settings[def.key]}"
            >
        `;
        controls.appendChild(block);

        const slider = block.querySelector("input");
        const valueLabel = block.querySelector(".value");

        const refreshLabel = () => {
            valueLabel.textContent = formatValue(def, slider.value);
        };

        refreshLabel();

        slider.addEventListener("input", () => {
            refreshLabel();
            clearTimeout(updateTimer);
            updateTimer = setTimeout(
                () => updateSetting(def, slider.value),
                130
            );
        });
    }

    refreshAeControlState();
}

async function updateSetting(def, rawValue) {
    const value = def.digits === 0
        ? Number.parseInt(rawValue, 10)
        : Number(rawValue);

    try {
        const response = await fetch("/api/settings", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({[def.key]: value}),
        });

        if (!response.ok) throw new Error(await response.text());
    } catch (error) {
        showMessage("Failed to apply setting: " + error.message);
    }
}

async function measureNeutral() {
    const targetKind = document.getElementById("target-kind").value;
    const box = document.getElementById("measurement");

    box.textContent = "Measuring…";

    try {
        const response = await fetch("/api/measure-neutral", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({target_kind: targetKind}),
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Measurement failed.");
        }

        lastMeasurement = data;
        const rec = data.recommended;

        box.innerHTML = `
            <div><b>Color diagnosis:</b> ${data.color_diagnosis}</div>
            <div><b>Exposure diagnosis:</b> ${data.exposure_diagnosis}</div>

            <div class="measure-grid">
                <div class="measure-item"><b>${data.median_r}</b>R medyan</div>
                <div class="measure-item"><b>${data.median_g}</b>G medyan</div>
                <div class="measure-item"><b>${data.median_b}</b>B medyan</div>
            </div>

            <div><b>WB recommendation:</b>
                R=${Number(rec.red_gain).toFixed(2)},
                G=${Number(rec.green_gain).toFixed(2)},
                B=${Number(rec.blue_gain).toFixed(2)}
            </div>
            <div><b>Exposure recommendation:</b> ${rec.exposure}</div>
            <div><b>ROI:</b>
                patlayan %${data.clipped_percent},
                dark %${data.dark_percent},
                valid %${data.valid_percent}
            </div>
            ${data.warning
                ? `<div class="warning">${data.warning}</div>`
                : `<div class="good">Measurement completed.</div>`
            }
        `;
    } catch (error) {
        lastMeasurement = null;
        box.innerHTML = `<span class="warning">${error.message}</span>`;
    }
}

async function applyRecommendation(applyWb, applyExposure) {
    if (!lastMeasurement) {
        showMessage("Measure the card first.");
        return;
    }

    try {
        const response = await fetch("/api/apply-recommendation", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                apply_wb: applyWb,
                apply_exposure: applyExposure,
            }),
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to apply recommendation.");
        }

        setSliderValues(data);
        showMessage("Recommendation applied. Check the image and undo it if necessary.");
    } catch (error) {
        showMessage(error.message);
    }
}

async function undoRecommendation() {
    try {
        const response = await fetch("/api/undo", {method:"POST"});
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Undo failed.");
        }

        setSliderValues(data);
        showMessage("Settings were restored to the state before the last recommendation.");
    } catch (error) {
        showMessage(error.message);
    }
}

async function startAutofocus() {
    const button = document.getElementById("autofocus");
    const info = document.getElementById("autofocus-info");

    autofocusRunning = true;
    refreshAeControlState();
    info.textContent = "Starting autofocus…";

    try {
        const response = await fetch("/api/autofocus", {method:"POST"});
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to start autofocus.");
        }

        showMessage(
            "Autofocus started. Keep the camera and target stationary until the scan completes."
        );
    } catch (error) {
        autofocusRunning = false;
        refreshAeControlState();
        info.textContent = error.message;
        showMessage(error.message);
    }
}

async function saveProfile() {
    const response = await fetch("/api/save", {method:"POST"});
    const data = await response.json();
    showMessage("Profile saved: " + data.path);
}

async function takeSnapshot() {
    const response = await fetch("/api/snapshot", {method:"POST"});
    const data = await response.json();

    if (!response.ok) {
        showMessage("Snapshot error: " + (data.detail || "unknown error"));
        return;
    }

    showMessage("Frame saved: " + data.path);
}

async function resetProfile(neutral) {
    const response = await fetch("/api/reset", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({neutral}),
    });
    const settings = await response.json();
    setSliderValues(settings);
    showMessage(
        neutral
            ? "RGB, gamma, contrast, and saturation values were set to 1.00."
            : "Recommended profile applied."
    );
}

function showMessage(text) {
    document.getElementById("message").textContent = text;
}

async function refreshStats() {
    try {
        const response = await fetch("/api/stats", {cache:"no-store"});
        const data = await response.json();

        document.getElementById("status").textContent =
            data.ready && data.running ? "Camera active" : "Waiting for camera";

        if (data.ready) {
            document.getElementById("mean-r").textContent = data.mean_r;
            document.getElementById("mean-g").textContent = data.mean_g;
            document.getElementById("mean-b").textContent = data.mean_b;
            document.getElementById("clipped").textContent =
                data.clipped_percent + "%";
            document.getElementById("dark").textContent =
                data.dark_percent + "%";

            const exposureSlider = document.getElementById("exposure");
            const exposureLabel = document.getElementById("exposure-value");
            if (exposureSlider && data.ae_mode === "auto") {
                const settingsResponse = await fetch(
                    "/api/settings",
                    {cache:"no-store"}
                );
                const currentSettings = await settingsResponse.json();
                exposureSlider.value = currentSettings.exposure;
                exposureLabel.textContent = currentSettings.exposure;
            }

            document.getElementById("ae-info").innerHTML = `
                <b>AE mode:</b> ${data.ae_mode}<br>
                <b>Raw clipping:</b> %${data.ae_raw_clipped_percent}<br>
                <b>Brightness percentiles:</b>
                P50=${data.ae_p50},
                P75=${data.ae_p75},
                P90=${data.ae_p90}<br>
                <b>Last action:</b> ${data.ae_last_action}
            `;

            const af = data.autofocus || {};
            autofocusRunning = Boolean(af.running);

            const focusSlider = document.getElementById("focus");
            const focusLabel = document.getElementById("focus-value");
            if (focusSlider && focusLabel && data.current_focus !== undefined) {
                focusSlider.value = data.current_focus;
                focusLabel.textContent = data.current_focus;
            }

            document.getElementById("autofocus-info").innerHTML = `
                <b>Durum:</b> ${af.phase || "idle"}<br>
                <b>Progress:</b> %${af.progress || 0}<br>
                <b>Current / best focus:</b>
                ${af.current_focus ?? "-"} / ${af.best_focus ?? "-"}<br>
                <b>Sharpness score:</b> ${af.best_score ?? 0}<br>
                <b>ROI texture deviation:</b> ${af.texture_std ?? 0}<br>
                <b>Message:</b> ${af.message || "Autofocus ready."}
            `;

            refreshAeControlState();
        }

        if (data.error) showMessage(data.error);
    } catch (_) {
        document.getElementById("status").textContent =
            "Server unreachable";
    }
}

async function init() {
    const response = await fetch("/api/settings");
    const settings = await response.json();
    buildControls(settings);

    document.getElementById("measure").onclick = measureNeutral;
    document.getElementById("apply-wb").onclick =
        () => applyRecommendation(true, false);
    document.getElementById("apply-exposure").onclick =
        () => applyRecommendation(false, true);
    document.getElementById("apply-both").onclick =
        () => applyRecommendation(true, true);
    document.getElementById("undo").onclick = undoRecommendation;
    document.getElementById("autofocus").onclick = startAutofocus;
    document.getElementById("save").onclick = saveProfile;
    document.getElementById("snapshot").onclick = takeSnapshot;
    document.getElementById("recommended").onclick =
        () => resetProfile(false);
    document.getElementById("neutral").onclick =
        () => resetProfile(true);

    refreshStats();
    setInterval(refreshStats, 1000);
}

init();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ.get("IMX230_HOST", "0.0.0.0"),
        port=int(os.environ.get("IMX230_PORT", "8000")),
        log_level="info",
        access_log=False,
    )
