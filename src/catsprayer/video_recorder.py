import os
import subprocess
import threading
import time
from picamera2.encoders import H264Encoder
from picamera2.outputs import CircularOutput


class VideoRecorder:
    """
    Continuously encodes the camera's main stream into an in-memory ring
    buffer (Picamera2's CircularOutput), so that when start() is called,
    the last `pre_event_seconds` of footage leading up to the event is
    already captured and gets included in the saved clip -- not just
    footage from the moment the cat was detected onward.

    The encoder runs for the entire lifetime of this object; start()/stop()
    only control whether the buffered+live stream is currently being
    written out to a file, not whether encoding itself is happening.
    """

    def __init__(self, camera, output_dir="data/videos", pre_event_seconds=2.0, fps=30):
        self.camera = self._find_raw_camera(camera)

        if self.camera is None:
            print("WARNING: Could not auto-detect raw Picamera2 instance. Defaulting to passed reference.")
            self.camera = camera

        self.output_dir = output_dir
        self.fps = fps
        self.recording = False

        self._current_h264_path = None
        self._current_mp4_path = None

        os.makedirs(self.output_dir, exist_ok=True)

        # CircularOutput's buffersize is a frame count, not a duration --
        # convert from the configured pre-event seconds using the camera's
        # framerate.
        buffer_frames = max(1, int(pre_event_seconds * fps))

        self.encoder = H264Encoder(bitrate=5000000)
        self.circular_output = CircularOutput(buffersize=buffer_frames)

        # Start continuous background encoding immediately. From this point
        # on the ring buffer is always populated with the last
        # pre_event_seconds of video, ready to be flushed to a file the
        # moment start() is called.
        self.camera.start_recording(self.encoder, self.circular_output, name="main")

    def _find_raw_camera(self, obj):
        if hasattr(obj, 'start_recording'):
            return obj
        for attr_name in ['_camera', 'camera', 'picam2', 'picamera2', 'cam', '_cam']:
            if hasattr(obj, attr_name):
                candidate = getattr(obj, attr_name)
                found = self._find_raw_camera(candidate)
                if found is not None:
                    return found
        return None

    def start(self):
        if self.recording:
            print("Already recording!")
            return

        timestamp = int(time.time())
        # Raw h264 goes to a temp file first (that's what CircularOutput
        # writes); it gets remuxed into the real .mp4 in stop().
        self._current_h264_path = os.path.join(self.output_dir, f"_recording_{timestamp}.h264")
        self._current_mp4_path = os.path.join(self.output_dir, f"recording_{timestamp}_new.mp4")

        print(f"Recording started (with pre-event buffer): {self._current_mp4_path}")

        # Flushes the buffered pre-event frames to this file first, then
        # keeps appending new frames as they arrive, until stop() is called.
        self.circular_output.fileoutput = self._current_h264_path
        self.circular_output.start()
        self.recording = True

    def stop(self):
        if not self.recording:
            return

        # Stops writing to this particular file; the encoder and circular
        # buffer keep running in the background for the next event.
        self.circular_output.stop()
        self.recording = False

        h264_path = self._current_h264_path
        mp4_path = self._current_mp4_path
        self._current_h264_path = None
        self._current_mp4_path = None

        # Run the remux on its own thread. This used to run synchronously
        # right here, which blocked whatever thread called stop() for
        # however long ffmpeg took -- and stop() is called from gui.py's
        # hardware loop, the same thread that continuously polls the
        # camera for AI detections. Blocking that thread for several
        # seconds right as a clip finishes is the strongest suspect for
        # the AI-channel stalls that were observed to coincide exactly
        # with a clip becoming available in the Review Queue.
        threading.Thread(
            target=self._remux_to_mp4,
            args=(h264_path, mp4_path),
            daemon=True,
        ).start()

        print("Recording stopped cleanly (pre-event footage included); remuxing in background.")

    def _remux_to_mp4(self, h264_path, mp4_path):
        """
        Losslessly wraps the raw h264 stream (which already includes the
        buffered pre-event frames) into a playable .mp4 container via
        ffmpeg, without re-encoding.
        """

        if h264_path is None or mp4_path is None:
            return

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-r", str(self.fps),
                    "-i", h264_path,
                    "-c", "copy",
                    mp4_path,
                ],
                check=True,
                capture_output=True,
            )
        except Exception as e:
            print(f"Notice: failed to remux recording to mp4 ({h264_path}): {e}")
        finally:
            if os.path.exists(h264_path):
                os.remove(h264_path)

    def cleanup(self):
        if self.recording:
            self.stop()

        try:
            self.camera.stop_encoder(self.encoder)
        except Exception as e:
            print(f"Notice during encoder cleanup: {e}")
