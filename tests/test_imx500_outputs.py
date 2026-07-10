from src.catsprayer.imx500 import IMX500Camera
import time


camera = IMX500Camera()

camera.start()

print("Camera started")

time.sleep(3)

outputs = camera.get_outputs()

print("\nOUTPUT TYPE:")
print(type(outputs))

print("\nNUMBER OF OUTPUTS:")
print(len(outputs))

for i, output in enumerate(outputs):

    print("\nOUTPUT", i)

    print("shape:", output.shape)

    print("first values:")
    print(output.flatten()[:10])


camera.stop()
