"""
Cat detection event recorder.

Records while a cat is detected.
Stops recording after the cat leaves.
"""

from __future__ import annotations

import time
from datetime import datetime

from catsprayer.video_recorder import VideoRecorder


class EventRecorder:

    def __init__(
        self,
        camera,
        output_directory="data/videos",
        post_event_delay=5.0,
    ):
        self.camera = camera
        self.post_event_delay = post_event_delay

        # Extract the raw Picamera2 instance from the IMX500 wrapper
        if hasattr(camera, "picam2"):
            raw_camera = camera.picam2
        elif hasattr(camera, "_camera"):
            raw_camera = camera._camera
        else:
            raw_camera = camera

        self.recorder = VideoRecorder(
            raw_camera,
            output_directory,
        )

        self.recording = False
        self.last_detection_time = 0
        self.state = "WAITING_FOR_CAT"

    def update(
        self,
        cat_detected: bool
    ):
        now = time.time()

        if cat_detected:
            self.last_detection_time = now

            if not self.recording:
                self.start()

        if (
            self.recording
            and
            now - self.last_detection_time
            >=
            self.post_event_delay
        ):
            self.stop()

    def start(self):
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        self.state = "RECORDING"

        print()
        print(
            f"STATE: {self.state}"
        )
        print(
            f"Starting cat recording {timestamp}"
        )

        self.recorder.start()
        self.recording = True

    def stop(self):
        if not self.recording:
            return

        self.state = "SAVING_VIDEO"
        print()
        print(
            f"STATE: {self.state}"
        )

        self.recorder.stop()
        self.recording = False
        self.state = "WAITING_FOR_CAT"

        print(
            "Recording stopped"
        )
        print(
            f"STATE: {self.state}"
        )
        print(
            "Waiting for cat..."
        )
        print()

    def cleanup(self):
        self.stop()
