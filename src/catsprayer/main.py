"""
CatSprayer Main Application
"""

from __future__ import annotations

import time

from catsprayer.imx500 import IMX500Camera
from catsprayer.detector import CatDetector
from catsprayer.sprayer import SprayerController
from catsprayer.event_recorder import EventRecorder
from catsprayer.config import CONFIG



def main():

    print()
    print("============================")
    print("   CatSprayer Starting")
    print("============================")
    print()


    camera = IMX500Camera()


    detector = CatDetector(
        confidence_threshold=
            CONFIG["detector"]["confidence_threshold"],

        required_detections=
            CONFIG["detector"]["required_detections"],

        trigger_delay=
            CONFIG["detector"]["trigger_delay"],

        cooldown_time=
            CONFIG["detector"]["cooldown_time"],
    )


    sprayer = SprayerController()


    event_recorder = EventRecorder(
        camera
    )



    try:

        camera.start()

        print("Camera running")
        print("Waiting for cat...")
        print("Press Ctrl+C to stop")
        print()


        while True:


            detections = camera.get_detections()


            result = detector.process(
                detections
            )


            #
            # Video recording follows cat presence
            #

            event_recorder.update(
                result["cat_detected"]
            )



            #
            # Display detection information
            #

            if result["cat_detected"]:

                print(
                    f"Cat "
                    f"{result['confidence']:.2f} "
                    f"Trigger={result['trigger']}"
                )



            #
            # LED / sprayer trigger
            #

            if result["trigger"]:

                print(
                    ">>> SPRAYER TRIGGERED <<<"
                )

                sprayer.activate()



            time.sleep(0.25)



    except KeyboardInterrupt:

        print()
        print("Stopping CatSprayer")



    finally:

        event_recorder.cleanup()

        camera.stop()

        sprayer.cleanup()



if __name__ == "__main__":

    main()
