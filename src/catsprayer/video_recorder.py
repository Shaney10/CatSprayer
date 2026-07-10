"""
Video recording support for CatSprayer.

Uses Picamera2 video recording.
"""

from pathlib import Path
import time

from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput


class VideoRecorder:

    def __init__(self, camera, output_directory="recordings"):

        self.camera = camera.picam2

        self.output_directory = Path(output_directory)

        self.output_directory.mkdir(
            exist_ok=True
        )

        self.encoder = H264Encoder()

        self.recording = False


    def start(self):

        if self.recording:
            return


        filename = (
            self.output_directory /
            f"recording_{int(time.time())}.mp4"
        )


        self.output = FfmpegOutput(
            str(filename)
        )


        self.camera.start_recording(
            self.encoder,
            self.output
        )


        self.recording = True

        print(
            f"Recording started: {filename}"
        )


    def stop(self):

        if not self.recording:
            return


        self.camera.stop_recording()

        self.recording = False

        print(
            "Recording stopped"
        )
