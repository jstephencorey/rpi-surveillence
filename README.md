# Raspberry Pi Surveillence Camera Setup (Headless)

This guide sets up a Raspberry Pi Zero 2 W (or similar Pi with a CSI camera) to automatically record or stream video from boot.

It assumes:

Raspberry Pi OS Lite (Bookworm or newer) (you can do 64 bit, apparently it's slightly better for this.)

Headless setup (SSH only, no GUI)

Official Raspberry Pi Camera Module or compatible (in this I'm using the )

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
`ssh pi@pi-cam-01.local`
(or use the Pi’s IP address)

`sudo apt update && sudo apt upgrade -y`

verify has rpicam:
`which rpicam-still` should return something.

`sudo apt install -y ffmpeg v4l-utils git motion vim` (vim is optional but I prefer it)

Edit `/boot/firmware/config.txt` with `sudo vim /boot/firmware/config.txt` (see here: https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/12MP-IMX708/)
    change `camera_auto_detect=1` to `camera_auto_detect=0`
    Locate the line [all] and add the following line below it:
        `dtoverlay=imx708` (you may need it to be different depending on what camera you have. Check out the arducam docs for more info)
    reboot with `sudo reboot`

check that it recognied the camera with `rpicam-still --list-cameras`
test with `rpicam-hello -t 5000`

### Set up for recording:

Clone this repo into the rpi: `git clone https://github.com/jstephencorey/rpi-surveillence.git`
Go into it with `cd rpi-surveillence`
Make the setup file runnable with `chmod +x setup.sh capture.py motion_postprocess.py`
Run the setup `sudo ./setup.sh`
reboot with `sudo reboot`



## Path forwards:

Fix the first-run startup processing stuff. 
Set up a server endpoint to recieve and re-transcode the H264 media to H265 (copy the old flask endpoint I have and add ffmpeg? Comment out the immich stuff for now/make that a different endpoint?)
    For now, store them locally on my server. Immich upload later. 
Get uploading set up (to server or immich directly)
Get Encoding set up (and jupyter or something to de-encode.)
Get physical stuff set up? switch, battery, etc.(3d printing?)