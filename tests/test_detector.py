from src.catsprayer.detector import CatDetector
import time


detector = CatDetector()


detections = [
    {
        "label": "cat",
        "class_id": 16,
        "confidence": 0.78,
        "box": (812,414,1103,653)
    }
]


for i in range(5):

    result = detector.process(detections)

    print(result)

    time.sleep(0.5)
