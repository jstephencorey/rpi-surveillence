# Raspberry Pi Surveillence Camera Setup (Headless)

This guide sets up a Raspberry Pi Zero 2 W (or similar Pi with a CSI camera) to automatically record or stream video from boot.

It assumes:

Raspberry Pi OS Lite (Bookworm or newer)

Headless setup (SSH only, no GUI)

Official Raspberry Pi Camera Module or compatible

## Flash Raspberry Pi OS

Download Raspberry Pi Imager

Select Raspberry Pi OS Lite (64-bit).

Configure advanced settings:

    Enable SSH

    Set username/password

    Configure WiFi (SSID + password + country)

    Set hostname (e.g., pi-cam-01)

Flash to microSD and boot the Pi.

### Setup:
ssh pi@pi-cam-01.local
(or use the Pi’s IP address)

sudo apt update && sudo apt upgrade -y

sudo apt install -y libcamera-apps ffmpeg v4l-utils git motion


