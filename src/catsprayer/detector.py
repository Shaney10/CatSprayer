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
        trigger_zones: list[tuple[float, float, float, float]] | None = None,
        exclusion_zones: list[tuple[float, float, float, float]] | None = None,
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

        # Zones are rectangles (x1, y1, x2, y2), normalized 0.0-1.0 as a
        # fraction of frame width/height.
        #
        # A cat is eligible to trigger the sprayer if its detection box is
        # centered inside at least one trigger zone (or there are NO trigger
        # zones defined at all, meaning the whole frame counts), AND it is
        # NOT centered inside any exclusion zone. Exclusion always wins.
        self.trigger_zones = list(trigger_zones) if trigger_zones else []
        self.exclusion_zones = list(exclusion_zones) if exclusion_zones else []

        # Detection boxes arrive as absolute pixel coordinates in this
        # resolution (see IMX500Camera.get_detections(), which calls
        # convert_inference_coords() to produce 1920x1080-space pixels).
        # These must match the camera's actual main-stream size, since
        # they're used to normalize boxes before comparing to zones.
        self.frame_width = frame_width
        self.frame_height = frame_height


        self.detection_count = 0
        self.cat_start_time = None
        self.last_trigger_time = 0


    def set_zones(
        self,
        trigger_zones: list[tuple[float, float, float, float]],
        exclusion_zones: list[tuple[float, float, float, float]],
    ) -> None:
        """
        Replace the full set of trigger/exclusion zones at once (e.g. on
        startup, loading from config). Resets in-progress detection
        counting, since changed zones invalidate any streak building up
        under the old ones.
        """

        self.trigger_zones = list(trigger_zones)
        self.exclusion_zones = list(exclusion_zones)
        self.detection_count = 0
        self.cat_start_time = None


    def add_trigger_zone(self, zone: tuple[float, float, float, float]) -> None:
        self.trigger_zones.append(zone)
        self.detection_count = 0
        self.cat_start_time = None


    def add_exclusion_zone(self, zone: tuple[float, float, float, float]) -> None:
        self.exclusion_zones.append(zone)
        self.detection_count = 0
        self.cat_start_time = None


    def remove_trigger_zone(self, index: int) -> None:
        if 0 <= index < len(self.trigger_zones):
            del self.trigger_zones[index]
            self.detection_count = 0
            self.cat_start_time = None


    def remove_exclusion_zone(self, index: int) -> None:
        if 0 <= index < len(self.exclusion_zones):
            del self.exclusion_zones[index]
            self.detection_count = 0
            self.cat_start_time = None


    def _zone_status(
        self,
        box: tuple[float, float, float, float]
    ) -> tuple[bool, list[int], list[int]]:
        """
        Returns (eligible, active_trigger_indices, active_exclusion_indices).

        active_trigger_indices / active_exclusion_indices list which zones
        (by index into self.trigger_zones / self.exclusion_zones) currently
        contain the cat's center point -- used by the GUI to highlight the
        specific zone(s) the cat is standing in.
        """

        # box arrives as absolute pixel coordinates (see class docstring
        # above); normalize to a 0.0-1.0 fraction of the frame before
        # comparing against zones, which are always normalized.
        x1, y1, x2, y2 = box
        cx = (x1 + x2) / 2 / self.frame_width
        cy = (y1 + y2) / 2 / self.frame_height

        active_trigger_indices = [
            i for i, (zx1, zy1, zx2, zy2) in enumerate(self.trigger_zones)
            if zx1 <= cx <= zx2 and zy1 <= cy <= zy2
        ]
        active_exclusion_indices = [
            i for i, (zx1, zy1, zx2, zy2) in enumerate(self.exclusion_zones)
            if zx1 <= cx <= zx2 and zy1 <= cy <= zy2
        ]

        if active_exclusion_indices:
            eligible = False
        elif not self.trigger_zones:
            eligible = True
        else:
            eligible = bool(active_trigger_indices)

        return eligible, active_trigger_indices, active_exclusion_indices



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
                "active_trigger_indices": [],
                "active_exclusion_indices": [],
            }



        #
        # Valid cat found
        #

        eligible, active_trigger_indices, active_exclusion_indices = self._zone_status(cat["box"])

        if not eligible:
            # Cat is visible but not zone-eligible (outside all trigger
            # zones, or inside an exclusion zone): don't let it build
            # toward a trigger, but still report it as detected so the
            # GUI can show the cat without implying a spray is imminent.
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
                "active_trigger_indices": active_trigger_indices,
                "active_exclusion_indices": active_exclusion_indices,
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

            "active_trigger_indices": active_trigger_indices,

            "active_exclusion_indices": active_exclusion_indices,
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
