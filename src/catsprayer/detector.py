"""
Cat detection logic.

Filters IMX500 detections and prepares
sprayer trigger decisions.
"""

import time


class CatDetector:

    def __init__(
        self,
        confidence_threshold=0.70,
        required_time=1.0,
    ):

        self.confidence_threshold = (
            confidence_threshold
        )

        self.required_time = required_time

        self.cat_start_time = None



    def update(self, detections):

        cat = None


        #
        # Find highest confidence cat
        #
        for detection in detections:

            if detection["label"] != "cat":
                continue


            if (
                detection["confidence"]
                <
                self.confidence_threshold
            ):
                continue


            cat = detection
            break



        #
        # No cat detected
        #
        if cat is None:

            self.cat_start_time = None

            return {
                "cat_detected": False,
                "trigger": False,
                "detection": None,
            }



        #
        # Start timer
        #
        if self.cat_start_time is None:

            self.cat_start_time = time.time()



        visible_time = (
            time.time()
            -
            self.cat_start_time
        )


        return {
            "cat_detected": True,

            "trigger":
                visible_time >= self.required_time,

            "visible_time":
                visible_time,

            "detection":
                cat,
        }
