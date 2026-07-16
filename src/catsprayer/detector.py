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
        trigger_zone: tuple[float, float, float, float] | None = None,
        frame_width: int = 1920,
        frame_height: int = 1080,
    ):

        self.confidence_threshold = confidence_threshold

        # Number of valid frames required
        self.required_detections = required_detections

        # How long cat must remain detected
        self.trigger_delay = trigger_delay

        # Prevent repeated spraying
        self.cooldown_time = cooldown_time

        # Optional rectangle (x1, y1, x2, y2), normalized 0.0-1.0 as a
        # fraction of frame width/height. If set, only cats whose detection
        # box is centered inside this zone count toward triggering the
        # sprayer. None (the default) means the whole frame is eligible.
        self.trigger_zone = trigger_zone

        # Detection boxes arrive as absolute pixel coordinates in this
        # resolution (see IMX500Camera.get_detections(), which calls
        # convert_inference_coords() to produce 1920x1080-space pixels).
        # These must match the camera's actual main-stream size, since
        # they're used to normalize boxes before comparing to trigger_zone.
        self.frame_width = frame_width
        self.frame_height = frame_height


        self.detection_count = 0
        self.cat_start_time = None
        self.last_trigger_time = 0


    def set_trigger_zone(
        self,
        zone: tuple[float, float, float, float] | None
    ) -> None:
        """
        Update the trigger zone at runtime (e.g. when the user repositions
        the box in the GUI). Passing None disables the zone restriction.
        Also resets in-progress detection counting, since a moved zone
        invalidates any streak that was building up under the old one.
        """

        self.trigger_zone = zone
        self.detection_count = 0
        self.cat_start_time = None


    def _center_in_zone(
        self,
        box: tuple[float, float, float, float]
    ) -> bool:
        if self.trigger_zone is None:
            return True

        # box arrives as absolute pixel coordinates (see class docstring
        # above); normalize to a 0.0-1.0 fraction of the frame before
        # comparing against trigger_zone, which is always normalized.
        x1, y1, x2, y2 = box
        cx = (x1 + x2) / 2 / self.frame_width
        cy = (y1 + y2) / 2 / self.frame_height

        zx1, zy1, zx2, zy2 = self.trigger_zone

        return (
            zx1 <= cx <= zx2
            and
            zy1 <= cy <= zy2
        )



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
                "in_zone": False,
            }



        #
        # Valid cat found
        #

        in_zone = self._center_in_zone(cat["box"])

        if not in_zone:
            # Cat is visible but outside the trigger zone: don't let it
            # build toward a trigger, but still report it as detected so
            # the GUI can show the cat without implying a spray is imminent.
            self.detection_count = 0
            self.cat_start_time = None

            return {
                "cat_detected": True,
                "trigger": False,
                "confidence": cat["confidence"],
                "box": cat["box"],
                "detections": self.detection_count,
                "elapsed": 0,
                "cooldown": False,
                "in_zone": False,
            }

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

            "in_zone": True,
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
