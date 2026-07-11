"""
CatSprayer Main Application
"""

from __future__ import annotations

import os
import sys

# --- FORCE LOCAL PI DISPLAY FOR REMOTE SSH ---
# If running over SSH and DISPLAY isn't set, force it to target the Pi's local desktop screen (:0)
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"

# Automatically resolve and inject the correct XDG runtime directory for the active user
if "XDG_RUNTIME_DIR" not in os.environ:
    try:
        # Matches the shell's /run/user/$(id -u)
        uid = os.getuid()
        os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    except AttributeError:
        pass  # Fallback for non-POSIX platforms
# ---------------------------------------------

import time
import cv2

from catsprayer.imx500 import IMX500Camera
from catsprayer.detector import CatDetector
from catsprayer.sprayer import SprayerController
from catsprayer.event_recorder import EventRecorder
from catsprayer.config import CONFIG


def main():

    print()
    print("============================")
    print("    CatSprayer Starting")
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

        print("Camera running")
        print("Waiting for cat...")
        print("Press 'q' in the video window or Ctrl+C to stop")
        print()

        # Flag to configure window properties once on startup
        window_initialized = False
        window_name = "CatSprayer IMX500"

        while True:
            # 1. Get the detections metadata for the processing pipeline
            detections = camera.get_detections()

            result = detector.process(detections)

            # Video recording follows cat presence
            event_recorder.update(result["cat_detected"])

            # Display detection information in terminal
            if result["cat_detected"]:
                print(
                    f"Cat "
                    f"{result['confidence']:.2f} "
                    f"Trigger={result['trigger']}"
                )

            # LED / sprayer trigger
            if result["trigger"]:
                print(">>> SPRAYER TRIGGERED <<<")
                sprayer.activate()

            # 2. Grab and display the frame with boxes directly on display :0
            frame = camera.get_annotated_frame()

            if frame is not None:
                cv2.imshow(window_name, frame)
                
                # Configure the window to be maximized/fullscreen on the very first frame
                if not window_initialized:
                    cv2.setWindowProperty(
                        window_name, 
                        cv2.WND_PROP_FULLSCREEN, 
                        cv2.WINDOW_FULLSCREEN
                    )
                    window_initialized = True
            
            # Watch for the exit key inside the window
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                print("Exiting via video window quit shortcut...")
                break
            
            time.sleep(0.01)

    except KeyboardInterrupt:
        print()
        print("Stopping CatSprayer")

    finally:
        event_recorder.cleanup()
        camera.stop()
        sprayer.cleanup()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
