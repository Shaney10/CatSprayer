from src.catsprayer.sprayer import SprayerController


sprayer = SprayerController(
    spray_duration=2
)


print("Testing sprayer")

sprayer.activate()

print("Test complete")
