"""
Video recording support for CatSprayer.

Uses Picamera2 video recording.
Supports multiple recordings.
"""

import time

from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput

from catsprayer.paths import VIDEOS_DIR



class VideoRecorder:


    def __init__(
        self,
        camera,
        output_directory=VIDEOS_DIR,
    ):

        self.camera = camera.picam2

        self.output_directory = output_directory


        self.output_directory.mkdir(
            exist_ok=True
        )


        self.encoder = None

        self.output = None

        self.recording = False



    def start(self):

        if self.recording:
            return


        filename = (
            self.output_directory
            /
            f"recording_{int(time.time())}.mp4"
        )


        #
        # Create new encoder each time
        #

        self.encoder = H264Encoder()


        self.output = FfmpegOutput(
            str(filename)
        )


        print(
            f"Recording started: {filename}"
        )


        self.camera.start_recording(
            self.encoder,
            self.output
        )


        self.recording = True



    def stop(self):

        if not self.recording:
            return


        self.camera.stop_recording()


        self.recording = False


        #
        # Release objects
        #

        self.encoder = None

        self.output = None


        print(
            "Recording stopped"
        )
