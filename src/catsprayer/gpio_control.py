"""
Raspberry Pi GPIO Control

Controls output pins used by CatSprayer.
"""

from __future__ import annotations

import lgpio

from catsprayer.config import CONFIG



class GPIOControl:


    def __init__(
        self,
        pin=None
    ):

        if pin is None:

            pin = CONFIG["sprayer_pin"]


        self.pin = pin

        self.handle = lgpio.gpiochip_open(0)


        lgpio.gpio_claim_output(
            self.handle,
            self.pin,
            0
        )


    def on(self):

        lgpio.gpio_write(
            self.handle,
            self.pin,
            1
        )


    def off(self):

        lgpio.gpio_write(
            self.handle,
            self.pin,
            0
        )


    def cleanup(self):

        self.off()

        lgpio.gpiochip_close(
            self.handle
        )
