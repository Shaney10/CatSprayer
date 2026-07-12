# CatSprayer Intelligent GUI Dashboard

AI-powered, vision-driven containment dashboard designed for Raspberry Pi to detect target activity and manage localized hardware peripherals.

## Description

The CatSprayer Intelligent GUI Dashboard coordinates an advanced detection system leveraging the IMX500 hardware accelerator. The application features a unified Tkinter graphical control dashboard, real-time camera tracking, event logs, automated video recording, and direct GPIO signal management for active deterrent hardware. It is built to operate completely standalone as a headless device that initializes straight into the control panel upon power delivery.

## Getting Started

### Dependencies

* **Operating System:** Raspberry Pi OS (64-bit) with Desktop initialized to **Display Auto-Login**.
* **System Packages:** `python3-pip`, `python3-venv`, `python3-tk`, libatlas-base-dev
* **Hardware Requirements:** Raspberry Pi camera module, IMX500 AI accelerator, and configured GPIO relay connections.

### Installing

1. Clone the project repository into your home directory:
   ```bash
   git clone <your-repo-link> ~/CatSprayer

Navigate into the workspace folder:

Bash
cd ~/CatSprayer
Initialize the isolated Python virtual environment:

Bash
python3 -m venv .venv
source .venv/bin/activate
Upgrade the package manager and install the project in editable deployment mode:

Bash
pip install --upgrade pip
pip install -e .
Executing program
Running Manually over SSH
To manually start the program over an active network shell session, you must explicitly route the execution loop to your primary connected monitor display:

Bash
cd ~/CatSprayer
source .venv/bin/activate
DISPLAY=:0 python -m src.catsprayer.main
Configuring Automated Launch on System Power-Up
Create the local desktop autostart profile directory:

Bash
mkdir -p ~/.config/autostart
Open the autostart entry configuration file using a text editor:

Bash
nano ~/.config/autostart/catsprayer.desktop
Insert the following initialization script block entirely into the file:

Ini, TOML
[Desktop Entry]
Type=Application
Name=CatSprayer
Exec=bash -c "cd /home/haney/CatSprayer && source .venv/bin/activate && python -m src.catsprayer.main"
WorkingDirectory=/home/haney/CatSprayer
Terminal=false
Save and exit (Ctrl+O, Enter, Ctrl+X), then cycle the system hardware power via a restart to verify automatic presentation:

Bash
sudo reboot
Help
If the graphical interface fails to populate on screen following a device restart, verify that the active window display environment is not locked out by evaluating local Python import structures manually:

Bash
DISPLAY=:0 python -m src.catsprayer.main
Common Fixes: Ensure your Raspberry Pi is configured via sudo raspi-config under System Options -> Boot / Auto Login to route directly to Desktop Autologin. If the user session pauses on a password lock screen, background system initializers will fail to resolve.

Authors
Haney

Version History
0.1

Initial Release

Verified local virtual environment structures and operational IMX500 integration routines.

Integrated custom .desktop workspace engine to force headless launch configurations.

License
This project is licensed under the [NAME HERE] License - see the LICENSE.md file for details

Acknowledgments
Raspberry Pi AI Module Camera framework documentation

awesome-readme




