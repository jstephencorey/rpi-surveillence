#!/bin/bash
set -e

TARGET_DIRECTORY="/home/piuser"
VIDEOS_DIR="$TARGET_DIRECTORY/videos"


echo "Creating video directories..."
mkdir -p -m 755 "$VIDEOS_DIR/buffer" "$VIDEOS_DIR/clips"
sudo chown -R piuser:piuser $VIDEOS_DIR

echo "Installing ffmpeg and python libraries..."
sudo apt install -y ffmpeg python3-opencv python3-numpy python3-dotenv

echo "Stopping/disabling old services..."
# Function to check if a service exists
service_exists() {
    systemctl list-unit-files "$1" &>/dev/null
    return $?
}

# Stop and disable services if they exist
if service_exists "capture.service"; then
    sudo systemctl stop capture.service
    sudo systemctl disable capture.service
fi

if service_exists "motion_postprocess.service"; then
    sudo systemctl stop motion_postprocess.service
    sudo systemctl disable motion_postprocess.service
fi

if service_exists "clip_uploader.service"; then
    sudo systemctl stop clip_uploader.service
    sudo systemctl disable clip_uploader.service
fi

echo "Installing systemd services..."
sudo cp /home/piuser/rpi-surveillence/capture.service /etc/systemd/system/capture.service
sudo cp /home/piuser/rpi-surveillence/motion_postprocess.service /etc/systemd/system/motion_postprocess.service
sudo cp /home/piuser/rpi-surveillence/clip_uploader.service /etc/systemd/system/clip_uploader.service

sudo systemctl daemon-reload
sudo systemctl enable --now capture.service
sudo systemctl enable --now motion_postprocess.service
sudo systemctl enable --now clip_uploader.service

# to stop and disable a service for testing:
# sudo systemctl stop motion_postprocess.service
# sudo systemctl disable motion_postprocess.service

echo "✅ Setup complete. Recording should start now and at boot."
