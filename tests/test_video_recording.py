from src.catsprayer.imx500 import IMX500Camera
from src.catsprayer.video_recorder import VideoRecorder
import time


camera = IMX500Camera()

camera.start()


recorder = VideoRecorder(
    camera
)


try:

    recorder.start()

    time.sleep(10)


finally:

    recorder.stop()

    camera.stop()
