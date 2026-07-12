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


def main():
    print()
    print("============================")
    print("    CatSprayer GUI Starting")
    print("============================")
    print()

    camera = IMX500Camera()

    detector = CatDetector(
        confidence_threshold=CONFIG["detector"]["confidence_threshold"],
        required_detections=CONFIG["detector"]["required_detections"],
        trigger_delay=CONFIG["detector"]["trigger_delay"],
        cooldown_time=CONFIG["detector"]["cooldown_time"],
    )

    sprayer = SprayerController()
    event_recorder = EventRecorder(camera)

    try:
        camera.start()

        # Initialize the Tkinter Application Framework Container Context
        root = tk.Tk()

        # Construct and mount dashboard layout controllers
        app = CatSprayerGUI(root, camera, detector, sprayer, event_recorder)

        print("GUI Active. Monitoring Background Pipelines...")
        root.mainloop()

    except KeyboardInterrupt:
        print("\nStopping CatSprayer Application Frame Context.")

    finally:
        event_recorder.cleanup()
        camera.stop()
        sprayer.cleanup()
        print("Shutdown Cleanly.")


if __name__ == "__main__":
    main()
