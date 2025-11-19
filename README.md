# Raspberry Pi Surveillence Camera Setup (Headless)

This guide sets up a Raspberry Pi Zero 2 W (or similar Pi with a CSI camera) to automatically record or stream video from boot.

It assumes:

Raspberry Pi OS Lite (Bookworm or newer) (you can do 64 bit, apparently it's slightly better for this.)

Headless setup (SSH only, no GUI)

Official Raspberry Pi Camera Module or compatible (in this I'm using the IMX708 12 MP camera https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/12MP-IMX708/)

## Flash Raspberry Pi OS

Download Raspberry Pi Imager
Select Raspberry Pi OS Lite (64-bit).

Configure advanced settings:
    Enable SSH
    Set username/password (most of this assumes a username of `piuser`)
    Configure WiFi (SSID + password + country)
    Set hostname (e.g., pi-cam)

Flash to microSD and boot the Pi.

### Setup:
`ssh piuser@pi-cam.local`
(or use the Pi’s IP address)

`sudo apt update && sudo apt upgrade -y`

verify has rpicam:
`which rpicam-still` should return something.

`sudo apt install -y ffmpeg v4l-utils git motion vim` (vim is optional but I prefer it. This assumes you know vim, but you can just replace "vim" with "nano" as needed)

Edit `/boot/firmware/config.txt` with `sudo vim /boot/firmware/config.txt` (see here: https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/12MP-IMX708/)
    change `camera_auto_detect=1` to `camera_auto_detect=0`
    Locate the line [all] and add the following line below it:
        `dtoverlay=imx708` (you may need it to be different depending on what camera you have. Check out the arducam docs for more info)
    reboot with `sudo reboot`

check that it recognized the camera with `rpicam-still --list-cameras` (should return something)
test with `rpicam-hello -t 5000` (won't show anything when headless, but will log things out)

### Set up for recording:

Clone this repo into the rpi: `git clone https://github.com/jstephencorey/rpi-surveillence.git`
Go into it with `cd rpi-surveillence`
Make the setup file runnable with `chmod +x setup.sh capture.py motion_postprocess.py`
Run the setup `sudo ./setup.sh`
reboot with `sudo reboot`

for testing: `git stash; git pull; chmod +x setup.sh shutdown_services.sh capture.py motion_postprocess.py clip_uploader.py; sudo ./setup.sh`

### Set up the upload server:

This is set up to go on my personal server in a docker container. You'll likely need to change several things (e.g. the attached volume and it's reference in app.py) to make it work for you.
`git clone https://github.com/jstephencorey/rpi-surveillence.git`
`cd rpi-surveillence/flask_api`
edit the .env file with `vim .env`. Currently you just need to put it there, nothing is being used.
`docker compose up -d --build`
Verify it's working with postman or bruno or something. 

For testing: `cd ../; git pull; cd ./flask_api; docker compose up -d --build;` 


## Future plans:

First off, currently I have a working surveillance camera! It works and will save videos to my home server. That's a cool thing to have and celebrate (:
Server:
    send to temp folder instead of root before processing
    Add an av1 handling GPU to my server and add in situ AV1 processing 
        Let it run on my computer?
        Also testing to find the right settings for good compression and good enough quality. 
        Need a new server motherboard for that... 🥲
    Join videos next to each other? (e.g. partial/part_###, final?) - I think this would be good, especially with the discovered limit of ~100 mb files I can send from the rpi zero 2 w before it breaks. 
Rename the repo 🙈
    And rename references to this repo within it. 
Rpi:
    Set up a non-SD card drive to write to?
        Find out if that's actually better? idk, I think it's flash, still...
    Get Encryption set up (and jupyter or something to decrypt.)
At some point re-set-up everything from scratch on a new rpi to make sure it's all repeatable
Get physical stuff set up? switch, battery, etc.(3d printing?)