"""
Main entry point for CatSprayer.
"""

from catsprayer.config import Config


def main() -> None:
    """Start the CatSprayer application."""

    config = Config()

    print("=" * 50)
    print("CatSprayer")
    print("=" * 50)

    print(
        f"Camera: "
        f"{config.get('camera', 'width')}x"
        f"{config.get('camera', 'height')}"
    )

    print(
        f"Target: "
        f"{config.get('ai', 'target_class')}"
    )

    print(
        f"Confidence Threshold: "
        f"{config.get('ai', 'confidence_threshold')}"
    )


if __name__ == "__main__":
    main()
