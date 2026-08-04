"""
CatSprayer Main Application
"""

from __future__ import annotations

import os
import sys

# --- FORCE LOCAL PI DISPLAY FOR REMOTE SSH ---
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"

if "XDG_RUNTIME_DIR" not in os.environ:
    try:
        uid = os.getuid()
        os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    except AttributeError:
        pass
# ---------------------------------------------

import tkinter as tk
from catsprayer.imx500 import IMX500Camera
from catsprayer.detector import CatDetector
from catsprayer.sprayer import SprayerController
from catsprayer.event_recorder import EventRecorder
from catsprayer.config import CONFIG
from catsprayer.gui import CatSprayerGUI
from catsprayer.paths import VIDEOS_DIR
from catsprayer.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def main():
    print()
    print("============================")
    print("    CatSprayer GUI Starting")
    print("============================")
    print()
    logger.info("CatSprayer starting up")

    camera = IMX500Camera()

    detector = CatDetector(
        confidence_threshold=CONFIG["detector"]["confidence_threshold"],
        required_detections=CONFIG["detector"]["required_detections"],
        trigger_delay=CONFIG["detector"]["trigger_delay"],
        cooldown_time=CONFIG["detector"]["cooldown_time"],
        trigger_zones=[tuple(z) for z in CONFIG["detector"]["spray_zones"]],
        exclusion_zones=[tuple(z) for z in CONFIG["detector"]["exclusion_zones"]],
        frame_width=CONFIG["camera"]["width"],
        frame_height=CONFIG["camera"]["height"],
        # .get() with a fallback, not a hard key lookup: this setting is new
        # and won't exist yet in an existing pyproject.toml until it's saved
        # once via the Settings screen (or added manually).
        # Default 0.75 chosen from real measured data: this cat's detection
        # box maxed out around 63-67% even at its closest approach to the
        # lens, while a confirmed false positive (bug/glare near the lens
        # at night) measured 86-99%. 0.75 sits comfortably in that gap.
        max_box_fraction=CONFIG["detector"].get("max_box_fraction", 0.75),
    )

    sprayer = SprayerController()
    event_recorder = None
    app = None

    try:
        camera.start()

        # Must come after camera.start(): EventRecorder builds a VideoRecorder
        # that immediately starts continuous background recording (for the
        # pre-event ring buffer), which would otherwise auto-configure and
        # start the camera itself with the wrong settings before camera.start()
        # gets a chance to configure it properly.
        event_recorder = EventRecorder(
            camera,
            output_directory=str(VIDEOS_DIR),
            post_event_delay=CONFIG["recording"]["post_event_seconds"],
            pre_event_seconds=CONFIG["recording"]["pre_event_seconds"],
            fps=CONFIG["recording"]["fps"],
        )

        # Initialize the Tkinter Application Framework Container Context
        root = tk.Tk()

        # Construct and mount dashboard layout controllers
        app = CatSprayerGUI(root, camera, detector, sprayer, event_recorder)

        print("GUI Active. Monitoring Background Pipelines...")
        logger.info("GUI active, entering mainloop")
        root.mainloop()

    except KeyboardInterrupt:
        print("\nStopping CatSprayer Application Frame Context.")
        logger.info("Stopped via KeyboardInterrupt")

    except Exception:
        # Anything else that reaches here is an unhandled crash. Previously
        # this would just propagate with no persisted record -- if the app
        # ever needs to be manually restarted with no visible cause, this is
        # the first thing to check in the log file.
        logger.exception("Unhandled exception reached main() -- app is crashing")
        raise

    finally:
        if event_recorder is not None:
            event_recorder.cleanup()
        camera.stop()
        sprayer.cleanup()
        print("Shutdown Cleanly.")
        logger.info("Shutdown complete")

    if app is not None and getattr(app, "restart_requested", False):
        print("Restarting CatSprayer...")
        logger.info("Restart requested, re-executing process")
        os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == "__main__":
    main()
