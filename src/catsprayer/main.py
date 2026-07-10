"""
CatSprayer Main Application

Connects:
- Sony IMX500 AI Camera
- CatDetector
- SprayerController

Current sprayer output is simulated.
"""

from __future__ import annotations

import time

from catsprayer.imx500 import IMX500Camera
from catsprayer.detector import CatDetector
from catsprayer.sprayer import SprayerController


def main():

    print()
    print("============================")
    print("   CatSprayer Starting")
    print("============================")
    print()


    camera = IMX500Camera()


    detector = CatDetector(
        confidence_threshold=0.70,
        required_detections=5,
        trigger_delay=1.0,
        cooldown_time=10.0,
    )


    sprayer = SprayerController(
        spray_duration=1.0
    )


    try:

        camera.start()


        print("Camera running")
        print("Waiting for cat detection...")
        print("Press Ctrl+C to stop")
        print()


        while True:


            detections = camera.get_detections()


            result = detector.process(
                detections
            )


            if result["cat_detected"]:

                print(
                    f"Cat detected | "
                    f"Confidence: "
                    f"{result['confidence']:.2f} | "
                    f"Detections: "
                    f"{result.get('detections', 0)} | "
                    f"Trigger: "
                    f"{result['trigger']}"
                )


            else:

                print(
                    "No cat detected"
                )



            if result["trigger"]:

                print()
                print(
                    ">>> SPRAYER TRIGGERED <<<"
                )
                print()


                sprayer.activate()



            time.sleep(0.25)



    except KeyboardInterrupt:

        print()
        print("Stopping CatSprayer...")


    finally:

        camera.stop()

        print("Camera stopped")
        print("Shutdown complete")



if __name__ == "__main__":

    main()
