"""
Cat detection event recorder.

Records only when the sprayer actually triggers -- not on every mere cat
detection. Once a triggered recording is underway, it keeps running while
the cat remains detected (to capture it leaving/reacting), and stops once
neither a trigger nor a detection has occurred for post_event_delay.
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
        pre_event_seconds=2.0,
        fps=30,
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
            pre_event_seconds=pre_event_seconds,
            fps=fps,
        )

        self.recording = False
        self.last_detection_time = 0
        self.state = "WAITING_FOR_CAT"

    def update(
        self,
        cat_detected: bool,
        triggered: bool = False,
    ):
        now = time.time()

        if triggered:
            # A spray actually happened: this is the only thing allowed to
            # start a new recording.
            self.last_detection_time = now

            if not self.recording:
                self.start()

        elif cat_detected and self.recording:
            # Cat is still around after an already-triggered recording
            # started -- keep the recording alive (thanks to the pre-event
            # buffer, this doesn't need to start a new file, just extend
            # the current one), but detection alone never starts a fresh
            # recording on its own.
            self.last_detection_time = now

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
