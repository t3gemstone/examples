# Copyright (c) 2025 by T3 Foundation. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#     https://docs.t3gemstone.org/en/license
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

import os
import cv2
import sys
import time
import numpy as np
from threading import Thread, Lock
from http.server import BaseHTTPRequestHandler, HTTPServer
from tflite_runtime.interpreter import Interpreter, load_delegate


class VideoStream:
    def __init__(self, gst_pipeline: str):
        self.stream = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
        if not self.stream.isOpened():
            raise RuntimeError("The GStreamer pipeline could not be opened. Check the camera connection.")
        self.frame = None
        self.lock = Lock()
        self.running = False

    def start(self):
        self.running = True
        Thread(target=self._update, daemon=True).start()
        return self

    def _update(self):
        while self.running:
            ret, frame = self.stream.read()
            if ret:
                with self.lock:
                    self.frame = frame

    def read(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self):
        self.running = False
        self.stream.release()

class ObjectDetector:
    def __init__(self, model_dir, model_name="detect.tflite", labels_name="labelmap.txt",
                 threshold=0.5, artifacts=None, use_tidl=True):
        self.model_path = os.path.join(model_dir, model_name)
        self.labels_path = os.path.join(model_dir, labels_name)
        self.threshold = threshold
        self.artifacts = artifacts or os.path.join(model_dir, 'artifacts')
        self.use_tidl = use_tidl

        self.labels = self._load_labels()
        self.interpreter = self._create_interpreter()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        self.height, self.width = self.input_details[0]['shape'][1:3]
        self.floating_model = (self.input_details[0]['dtype'] == np.float32)

    def _load_labels(self):
        with open(self.labels_path, 'r') as f:
            labels = [line.strip() for line in f.readlines()]
        if labels and labels[0] == '???':
            labels.pop(0)
        return labels

    def _create_interpreter(self):
        if self.use_tidl:
            try:
                tidl_lib_candidates = [
                    '/usr/lib/libtidl_tfl_delegate.so',
                    'libtidl_tfl_delegate.so',
                    '/usr/lib/libtidl_tfl_delegate.so.1.0',
                ]
                tidl_lib = next((c for c in tidl_lib_candidates if os.path.exists(c)), 'libtidl_tfl_delegate.so')
                delegate_options = {
                    "artifacts_folder": self.artifacts,
                    "platform": "J7",
                    "version": "7.2",
                    "debug_level": 0
                }
                delegate = load_delegate(tidl_lib, delegate_options)
                print("TIDL delegate loaded successfully.")
                interpreter = Interpreter(model_path=self.model_path, experimental_delegates=[delegate])
            except Exception as e:
                print(f"TIDL delegate load failed: {e}")
                print("Falling back to CPU inference.")
                interpreter = Interpreter(model_path=self.model_path)
        else:
            interpreter = Interpreter(model_path=self.model_path)

        interpreter.allocate_tensors()
        return interpreter

    def infer(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(frame_rgb, (self.width, self.height))
        input_data = np.expand_dims(resized, axis=0)

        if self.floating_model:
            input_data = (np.float32(input_data) - 127.5) / 127.5

        self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
        self.interpreter.invoke()

        output = [self.interpreter.get_tensor(o['index']) for o in self.output_details]
        boxes, classes, scores = self._parse_outputs(output)
        return self._draw_boxes(frame, boxes, classes, scores)

    def _parse_outputs(self, output):
        outname = self.output_details[0]['name']
        boxes_idx, classes_idx, scores_idx = (1, 3, 0) if 'StatefulPartitionedCall' in outname else (0, 1, 2)
        boxes = output[boxes_idx][0]
        classes = output[classes_idx][0]
        scores = output[scores_idx][0]
        return boxes, classes, scores

    def _draw_boxes(self, frame, boxes, classes, scores):
        for i, score in enumerate(scores):
            if self.threshold < score <= 1.0:
                h, w = frame.shape[:2]
                ymin, xmin, ymax, xmax = (int(boxes[i][0] * h), int(boxes[i][1] * w),
                                          int(boxes[i][2] * h), int(boxes[i][3] * w))
                label = f"{self.labels[int(classes[i])]}: {int(score * 100)}%"
                cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (10, 255, 0), 2)
                cv2.putText(frame, label, (xmin, ymin - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        return frame

class MJPEGHandler(BaseHTTPRequestHandler):
    shared_frame = None
    lock = Lock()

    def do_GET(self):
        if self.path != '/video':
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.end_headers()

        while True:
            with MJPEGHandler.lock:
                if MJPEGHandler.shared_frame is None:
                    continue
                _, jpeg = cv2.imencode('.jpg', MJPEGHandler.shared_frame)

            self.wfile.write(b'--frame\r\n')
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', str(len(jpeg)))
            self.end_headers()
            self.wfile.write(jpeg.tobytes())
            self.wfile.write(b'\r\n')
            time.sleep(0.03)


class MJPEGServer(Thread):
    def __init__(self, host='0.0.0.0', port=8080):
        super().__init__(daemon=True)
        self.server = HTTPServer((host, port), MJPEGHandler)
        print(f"MJPEG server running at: http://{host}:{port}/video")

    def run(self):
        self.server.serve_forever()

class Application:
    def __init__(self, args):
        self.args = args
        self.detector = ObjectDetector(
            model_dir=args.modeldir,
            model_name=args.graph,
            labels_name=args.labels,
            threshold=float(args.threshold),
            artifacts=args.artifacts,
            use_tidl=not args.no_tidl
        )
        self.stream = VideoStream(self._gst_pipeline()).start()
        self.server = MJPEGServer()

    def _gst_pipeline(self):
        if self.args.device:
            return (
                f"v4l2src device={self.args.device} ! "
                "video/x-raw,format=YUY2,width=1280,height=720,framerate=30/1 ! "
                "videoconvert ! video/x-raw,format=BGR ! appsink drop=true sync=false"
            )
        
        return (
            "v4l2src device=/dev/video-imx219-cam0 ! "
            "video/x-bayer,width=1920,height=1080,format=rggb ! "
            "tiovxisp sink_0::device=/dev/v4l-subdev2 sensor-name=SENSOR_SONY_IMX219_RPI "
            "dcc-isp-file=/opt/imaging/imx219/linear/dcc_viss_1920x1080.bin "
            "sink_0::dcc-2a-file=/opt/imaging/imx219/linear/dcc_2a_1920x1080.bin format-msb=7 ! "
            "tiovxmultiscaler ! video/x-raw,format=NV12,width=1280,height=720 ! "
            "videoconvert ! video/x-raw,format=BGR ! appsink drop=true sync=false"
        )

    def run(self):
        self.server.start()
        print("Starting detection loop...")
        prev_time = time.time()
        try:
            while True:
                frame = self.stream.read()
                if frame is None:
                    continue

                frame = self.detector.infer(frame)
                fps = 1 / (time.time() - prev_time)
                prev_time = time.time()
                cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

                with MJPEGHandler.lock:
                    MJPEGHandler.shared_frame = frame

        except KeyboardInterrupt:
            print("Terminating...")
            self.stream.stop()