"""
Shared data models used throughout CatSprayer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BoundingBox:
    """
    Bounding box in image coordinates.
    """

    x: int
    y: int
    width: int
    height: int


@dataclass(slots=True)
class Detection:
    """
    One AI object detection.
    """

    label: str
    confidence: float
    bounding_box: BoundingBox
