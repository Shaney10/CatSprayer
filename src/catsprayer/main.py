"""
Main entry point for CatSprayer.
"""

from catsprayer.config import Config
from catsprayer.logger import configure_logging, get_logger


def main() -> None:
    configure_logging()

    logger = get_logger(__name__)

    config = Config()

    logger.info("CatSprayer starting")

    logger.info(
        "Camera: %sx%s",
        config.get("camera", "width"),
        config.get("camera", "height"),
    )

    logger.info(
        "Target: %s",
        config.get("detection", "target_class"),
    )

    logger.info(
        "Confidence threshold: %.2f",
        config.get("detection", "confidence_threshold"),
    )


if __name__ == "__main__":
    main()
