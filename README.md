# CatSprayer

AI-powered cat detection and automated water sprayer for Raspberry Pi, built around the Sony IMX500 AI camera accelerator. Runs as a standalone, touchscreen-friendly dashboard that boots straight into the control panel — no keyboard or monitor required after setup.

## Description

CatSprayer watches a camera feed for cats using on-camera AI inference (via the IMX500's built-in neural network accelerator, so detection runs on the camera itself rather than taxing the Pi's CPU), and triggers a GPIO-controlled sprayer when a cat is detected inside a user-defined zone. It's built entirely around a single Tkinter dashboard that covers live monitoring, clip review, and configuration — all designed to be operated by touch alone.

### Features

- **Live detection view** with bounding boxes and confidence scores drawn directly onto both the on-screen preview and any saved recordings, so you can always see exactly what triggered a spray.
- **Multiple spray zones and exclusion zones** — draw as many "spray if the cat is here" and "never spray here" rectangles as you want directly on the live video by dragging; exclusion always overrides a spray zone.
- **Pre-event recording** — a continuously running ring buffer means saved clips include a few seconds of footage *before* the triggering detection, not just after.
- **Recordings only save on an actual spray**, not on every cat detection, so you're not left digging through clips of cats that were never sprayed.
- **False-positive filtering**: a confidence threshold, a required-consecutive-detections counter, and a maximum detection-size filter (to reject implausibly large boxes typically caused by bugs, glare, or debris very close to the lens at night) all work together to cut down false triggers.
- **In-app Settings screen** — confidence threshold, required detections, trigger delay, cooldown time, and max detection size are all adjustable with tap-only +/- controls (no keyboard needed), saved directly to `pyproject.toml`, with a one-tap restart when you're done.
- **Review Queue** for newly recorded clips — Keep, Favorite, Delete, or Decide Later, plus a Favorites and full clip archive.
- **Slow-motion playback toggle** for reviewing clips frame-by-frame in detail.
- **Spray stats screen** — sprays today/this week/all-time and the most common hour, with a hold-3-seconds-to-confirm reset.

## Getting Started

### Dependencies

* **Operating System:** Raspberry Pi OS (64-bit), Desktop, with **Auto-Login to Desktop** enabled.
* **System packages:** `python3-pip`, `python3-venv`, `python3-tk`, `libatlas-base-dev`, `ffmpeg`
* **Hardware:** Raspberry Pi camera module with IMX500 AI accelerator, and a GPIO-connected relay driving the sprayer solenoid/pump.

### Installing

Clone the repository into your home directory:
```bash
git clone https://github.com/Shaney10/CatSprayer.git ~/CatSprayer
```

Move into the project folder and set up an isolated virtual environment:
```bash
cd ~/CatSprayer
python3 -m venv .venv
source .venv/bin/activate
```

Install the project (this also pulls in its Python dependencies, including `picamera2`, `numpy`, `lgpio`, and `tomlkit`):
```bash
pip install --upgrade pip
pip install -e .
```

### Configuration

Runtime settings (GPIO pin, spray duration, detector tuning, spray/exclusion zones, camera resolution, recording behavior) live in `pyproject.toml` under `[tool.catsprayer]`. Most of the detector-related values can also be changed live from the app itself via the **⚙️ Detector Settings** screen — those changes are written back to `pyproject.toml` automatically.

## Running the Program

### Manually, over SSH

To launch it manually while SSH'd in, route the display to the Pi's local screen:
```bash
cd ~/CatSprayer
source .venv/bin/activate
DISPLAY=:0 python -m catsprayer.main
```

### Automatic launch on boot

Create the autostart directory:
```bash
mkdir -p ~/.config/autostart
```

Create the autostart entry:
```bash
nano ~/.config/autostart/catsprayer.desktop
```

Paste in the following, adjusting the paths if your project isn't at `/home/haney/CatSprayer`:
```ini
[Desktop Entry]
Type=Application
Name=CatSprayer
Exec=bash -c "cd /home/haney/CatSprayer && source .venv/bin/activate && python -m catsprayer.main"
WorkingDirectory=/home/haney/CatSprayer
Terminal=false
```

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`), then reboot to confirm it launches automatically:
```bash
sudo reboot
```

## Troubleshooting

If the dashboard doesn't appear after a reboot, first confirm the Pi is actually configured to auto-login to the desktop (`sudo raspi-config` → System Options → Boot / Auto Login → Desktop Autologin) — background autostart entries won't run if the session is sitting at a login/lock screen.

If it still doesn't launch, try running it manually as shown above to see the actual error output:
```bash
DISPLAY=:0 python -m catsprayer.main
```

## Roadmap

- Package as a standalone installable application (e.g. via PyInstaller) instead of requiring a manual Python environment setup — planned, not yet started.

## Version History

**1.0**
- Full rewrite of the detection/recording/review pipeline: multi-zone spray + exclusion detection, pre-event ring-buffer recording, trigger-only (not detection-only) recording, and a max-detection-size false-positive filter.
- Detection boxes and confidence burned directly into both the live view and saved recordings.
- In-app Settings screen for live detector tuning, with automatic config persistence.
- Review Queue, Favorites, slow-motion playback, and spray statistics with reset.

**0.1**
- Initial release: local virtual environment setup and IMX500 camera integration, `.desktop`-based headless autostart.

## License

Not yet chosen. If you'd like the project to have explicit usage terms, add a `LICENSE` file and update this section accordingly.

## Authors

Haney

## Acknowledgments

- Raspberry Pi AI Camera (IMX500) documentation
- The [Picamera2](https://github.com/raspberrypi/picamera2) project
