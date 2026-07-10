from src.catsprayer.detector import CatDetector


detector = CatDetector()


detections = [
    {
        "label": "cat",
        "confidence": 0.78,
        "box": (812,414,1103,653)
    }
]


result = detector.update(detections)

print(result)
