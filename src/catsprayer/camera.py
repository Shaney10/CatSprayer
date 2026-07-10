"""
Camera interface for the Raspberry Pi AI Camera (IMX500).
"""

from __future__ import annotations

from typing import Any

from picamera2 import Picamera2

from catsprayer.config import Config
from catsprayer.logger import get_logger


class Camera:
    """
    Raspberry Pi AI Camera wrapper.
    """

    def __init__(self, config: Config) -> None:
        self._logger = get_logger(__name__)
        self._config = config

        self._camera = Picamera2()

        self._started = False

    def start(self) -> None:
        """
        Start the camera.
        """

        width = self._config.get("camera", "width")
        height = self._config.get("camera", "height")

        camera_config = self._camera.create_preview_configuration(
            main={
                "size": (width, height),
            }
        )

        self._camera.configure(camera_config)

        self._camera.start()

        self._started = True

        self._logger.info(
            "Camera started (%sx%s)",
            width,
            height,
        )

    def stop(self) -> None:
        """
        Stop the camera.
        """

        if self._started:
            self._camera.stop()
            self._started = False

            self._logger.info("Camera stopped")

    @property
    def started(self) -> bool:
        """
        Return True if the camera is running.
        """

        return self._started

    def capture_frame(self) -> Any:
        """
        Capture the latest frame.
        """

        return self._camera.capture_array()

    def capture_metadata(self) -> dict[str, Any]:
        """
        Capture camera metadata.
        """

        return self._camera.capture_metadata()
