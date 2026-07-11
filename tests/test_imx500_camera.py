"""
Test the Sony IMX500 AI Camera.

Displays:
- Live video
- Bounding boxes
- Labels
- Confidence

Press Q to quit.
"""

import cv2

from catsprayer.imx500 import IMX500Camera


def main():

    camera = IMX500Camera()

    camera.start()

    print()
    print("====================================")
    print(" IMX500 Camera Test")
    print(" Press Q to quit")
    print("====================================")
    print()

    last_detections = []

    try:

        while True:

            #
            # Get annotated frame
            #

            frame = camera.get_annotated_frame()

            #
            # Show detections in terminal only when they change
            #

            detections = camera.get_detections()

            if detections != last_detections:

                print("--------------------------------")

                if detections:

                    for det in detections:

                        print(
                            f'{det["label"]:10s} '
                            f'{det["confidence"]:.2f}   '
                            f'{det["box"]}'
                        )

                else:

                    print("No detections")

                last_detections = detections

            #
            # Display video
            #

            cv2.imshow(
                "CatSprayer IMX500",
                frame,
            )

            #
            # Quit
            #

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):

                break

    finally:

        camera.stop()

        cv2.destroyAllWindows()


if __name__ == "__main__":

    main()
