"""
Sony IMX500 AI Camera interface.

Provides:
- Live RGB video frames
- IMX500 MobileNet SSD object detection
- Pixel-correct bounding boxes
- Detection smoothing
"""

from __future__ import annotations

import time

import cv2

from picamera2 import Picamera2
from picamera2.devices.imx500 import IMX500

from catsprayer.logger import get_logger


MODEL_FILE = (
    "/usr/share/imx500-models/"
    "imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk"
)


class IMX500Camera:

    CLASS_NAMES = [
        "person", "bicycle", "car", "motorcycle", "airplane",
        "bus", "train", "truck", "boat", "traffic light",
        "fire hydrant", "unknown", "stop sign", "parking meter",
        "bench", "bird", "cat", "dog", "horse", "sheep",
        "cow", "elephant", "bear", "zebra", "giraffe",
        "unknown", "backpack", "umbrella", "unknown", "unknown",
        "handbag", "tie", "suitcase", "frisbee", "skis",
        "snowboard", "sports ball", "kite", "baseball bat",
        "baseball glove", "skateboard", "surfboard",
        "tennis racket", "bottle", "unknown", "wine glass",
        "cup", "fork", "knife", "spoon", "bowl", "banana",
        "apple", "sandwich", "orange", "broccoli", "carrot",
        "hot dog", "pizza", "donut", "cake", "chair",
        "couch", "potted plant", "bed", "unknown",
        "dining table", "unknown", "unknown", "toilet",
        "unknown", "tv", "laptop", "mouse", "remote",
        "keyboard", "cell phone", "microwave", "oven",
        "toaster", "sink", "refrigerator", "unknown",
        "book", "clock", "vase", "scissors", "teddy bear",
        "hair drier", "toothbrush"
    ]


    def __init__(self):

        self.logger = get_logger(__name__)

        self.imx500 = IMX500(MODEL_FILE)

        self.picam2 = Picamera2()

        self.config = (
            self.picam2.create_preview_configuration(
                main={
                    "size": (1920, 1080),
                    "format": "RGB888",
                },
                lores={
                    "size": (320, 320),
                    "format": "RGB888",
                }
            )
        )

        self.confidence_threshold = 0.50

        #
        # Detection smoothing
        #
        self.last_detections = []
        self.last_detection_time = 0
        self.detection_timeout = 0.75



    def start(self):

        self.picam2.configure(
            self.config
        )

        self.picam2.start()

        time.sleep(2)



    def stop(self):

        self.picam2.stop()



    def get_frame(self):

        return self.picam2.capture_array()



    def get_detections(self):

        metadata = (
            self.picam2.capture_metadata()
        )

        outputs = (
            self.imx500.get_outputs(metadata)
        )


        #
        # No inference result yet
        #
        if outputs is None:

            if (
                time.time()
                -
                self.last_detection_time
                >
                self.detection_timeout
            ):
                self.last_detections = []

            return self.last_detections



        boxes = outputs[0]
        scores = outputs[1]
        classes = outputs[2]


        detections = []


        for box, score, cls in zip(
            boxes,
            scores,
            classes
        ):

            score = float(score)


            if score < self.confidence_threshold:
                continue


            #
            # Convert neural network coordinates
            # into 1920x1080 display coordinates
            #
            x, y, w, h = (
                self.imx500.convert_inference_coords(
                    tuple(box),
                    metadata,
                    self.picam2,
                )
            )


            detections.append(
                {
                    "label":
                        self.CLASS_NAMES[int(cls)],

                    "class_id":
                        int(cls),

                    "confidence":
                        score,

                    "box":
                        (
                            int(x),
                            int(y),
                            int(x + w),
                            int(y + h),
                        )
                }
            )


        if detections:

            self.last_detections = detections

            self.last_detection_time = (
                time.time()
            )


        elif (
            time.time()
            -
            self.last_detection_time
            >
            self.detection_timeout
        ):

            self.last_detections = []


        return self.last_detections



    def get_annotated_frame(self):

        frame = self.get_frame()

        detections = self.get_detections()


        for det in detections:

            x1, y1, x2, y2 = det["box"]


            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                3,
            )


            text = (
                f'{det["label"]} '
                f'{det["confidence"]:.0%}'
            )


            #
            # Keep text visible if box is near top
            #
            text_y = max(
                y1 - 10,
                30
            )


            cv2.rectangle(
                frame,
                (x1, text_y - 28),
                (x1 + 220, text_y),
                (0, 255, 0),
                -1,
            )


            cv2.putText(
                frame,
                text,
                (x1 + 5, text_y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 0, 0),
                2,
            )


        return frame
