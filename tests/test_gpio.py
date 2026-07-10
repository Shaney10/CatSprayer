from catsprayer.gpio_control import GPIOControl
import time


gpio = GPIOControl()


print("GPIO test started")


try:

    print("ON")

    gpio.on()

    time.sleep(2)


    print("OFF")

    gpio.off()

    time.sleep(2)


finally:

    gpio.cleanup()

    print("GPIO cleanup complete")
