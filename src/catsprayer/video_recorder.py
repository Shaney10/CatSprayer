import os
import time
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput

class VideoRecorder:
    def __init__(self, camera, output_dir="data/videos"):
        self.camera = self._find_raw_camera(camera)
        
        if self.camera is None:
            print("WARNING: Could not auto-detect raw Picamera2 instance. Defaulting to passed reference.")
            self.camera = camera
            
        self.output_dir = output_dir
        self.recording = False
        
        self.encoder = None
        self.output = None

        os.makedirs(self.output_dir, exist_ok=True)

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

        # Generates a brand new unique filename using the current epoch timestamp with _new suffix
        filename = f"recording_{int(time.time())}_new.mp4"
        filepath = os.path.join(self.output_dir, filename)
        print(f"Recording started: {filepath}")

        # Build a fresh encoder and output stream
        self.encoder = H264Encoder(bitrate=5000000)
        self.output = FfmpegOutput(filepath)

        # Start recording on the main stream split
        self.camera.start_recording(self.encoder, self.output, name="main")
        self.recording = True

    def stop(self):
        if not self.recording:
            return

        # 1. Stop the specific encoder tied to the main stream
        if self.encoder:
            self.camera.stop_encoder(self.encoder)
        else:
            self.camera.stop_encoder()
            
        self.recording = False

        # 2. Close out the file safely
        if hasattr(self.output, 'close'):
            try:
                self.output.close()
            except Exception as e:
                print(f"Notice during output close: {e}")

        # 3. Wipe references completely so the next start() can rebuild fresh
        self.encoder = None
        self.output = None
        print("Recording stopped cleanly and objects reset.")

    def cleanup(self):
        if self.recording:
            self.stop()
