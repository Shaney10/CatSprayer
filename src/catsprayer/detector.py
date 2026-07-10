"""
CatSprayer Detection Module

Handles decision logic between:
IMX500 AI Camera detections
and the sprayer trigger.

Features:
- Confidence threshold
- Consecutive detection filtering
- Trigger delay
- Cooldown timer
"""

from __future__ import annotations

import time


class CatDetector:
    """
    Determines when a cat should trigger the sprayer.
    """


    def __init__(
        self,
        confidence_threshold: float = 0.70,
        required_detections: int = 5,
        trigger_delay: float = 1.0,
        cooldown_time: float = 10.0,
    ):

        self.confidence_threshold = confidence_threshold

        # Number of valid frames required
        self.required_detections = required_detections

        # How long cat must remain detected
        self.trigger_delay = trigger_delay

        # Prevent repeated spraying
        self.cooldown_time = cooldown_time


        self.detection_count = 0
        self.cat_start_time = None
        self.last_trigger_time = 0



    def process(
        self,
        detections: list[dict]
    ) -> dict:
        """
        Process camera detections.

        Returns:

        {
            cat_detected: bool,
            trigger: bool,
            confidence: float,
            box: tuple
        }

        """


        cat = self._find_cat(
            detections
        )


        #
        # No valid cat
        #

        if cat is None:

            self.detection_count = 0
            self.cat_start_time = None

            return {
                "cat_detected": False,
                "trigger": False,
                "confidence": 0,
                "box": None,
            }



        #
        # Valid cat found
        #

        self.detection_count += 1


        if self.cat_start_time is None:

            self.cat_start_time = time.time()



        elapsed = (
            time.time()
            -
            self.cat_start_time
        )


        #
        # Check cooldown
        #

        cooldown_active = (
            time.time()
            -
            self.last_trigger_time
            <
            self.cooldown_time
        )



        trigger = False


        if (
            self.detection_count
            >=
            self.required_detections
            and
            elapsed
            >=
            self.trigger_delay
            and
            not cooldown_active
        ):

            trigger = True

            self.last_trigger_time = time.time()

            self.detection_count = 0
            self.cat_start_time = None



        return {

            "cat_detected": True,

            "trigger": trigger,

            "confidence": cat["confidence"],

            "box": cat["box"],

            "detections": self.detection_count,

            "elapsed": elapsed,

            "cooldown": cooldown_active,
        }



    def _find_cat(
        self,
        detections
    ):
        """
        Find highest confidence cat.
        """

        best_cat = None


        for detection in detections:

            if detection.get("label") != "cat":
                continue


            confidence = detection.get(
                "confidence",
                0
            )


            if confidence < self.confidence_threshold:
                continue


            if (
                best_cat is None
                or
                confidence > best_cat["confidence"]
            ):

                best_cat = detection


        return best_cat
