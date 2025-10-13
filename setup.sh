#!/bin/bash
set -e

VIDEOS_DIR="/home/piuser/videos"

echo "Creating video directories..."
mkdir -p -m 755 "$VIDEOS_DIR/buffer" "$VIDEOS_DIR/clips"
sudo chown -R piuser:piuser /home/piuser/videos

echo "Installing ffmpeg and python libraries..."
sudo apt install -y ffmpeg python3-opencv python3-numpy

echo "Stopping/disabling old services..." #todo remove this eventually
sudo systemctl disable capture.service
sudo systemctl stop capture.service
sudo systemctl disable lores.service
sudo systemctl stop lores.service

echo "Installing systemd services..."
sudo cp /home/piuser/rpi-surveillence/capture.service /etc/systemd/system/capture.service
sudo cp /home/piuser/rpi-surveillence/lores.service /etc/systemd/system/lores.service

sudo systemctl daemon-reload
sudo systemctl enable --now capture.service
sudo systemctl enable --now lores.service

# to stop and disable a service for testing:
# sudo systemctl stop motion_postprocess.service
# sudo systemctl disable motion_postprocess.service

echo "✅ Setup complete. Recording should start now and at boot."
