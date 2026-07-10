from src.catsprayer.imx500 import IMX500Camera
from src.catsprayer.detector import CatDetector

import time


camera = IMX500Camera()

detector = CatDetector(
    confidence_threshold=0.70,
    required_detections=5,
    trigger_delay=1.0,
    cooldown_time=10.0
)


camera.start()


print("Live cat detection started")
print("Press Ctrl+C to stop")


try:

    while True:

        detections = camera.get_detections()


        result = detector.process(
            detections
        )


        if result["cat_detected"]:

            print(
                f"CAT "
                f"{result['confidence']:.2f} "
                f"{result['box']} "
                f"Trigger={result['trigger']}"
            )

        else:

            print(
                "No cat detected"
            )


        time.sleep(0.25)


except KeyboardInterrupt:

    print("Stopping")


finally:

    camera.stop()
