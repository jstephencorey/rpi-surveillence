#!/bin/bash
set -e

VIDEOS_DIR="/home/piuser/videos"

echo "Creating video directories..."
mkdir -p -m 755 "$VIDEOS_DIR/buffer" "$VIDEOS_DIR/clips"
sudo chown -R piuser:piuser /home/piuser/videos

echo "Installing ffmpeg and python libraries..."
sudo apt install -y ffmpeg python3-opencv python3-numpy

echo "Installing systemd services..."
sudo cp /home/piuser/rpi-surveillence/camera.service /etc/systemd/system/camera.service
sudo cp /home/piuser/rpi-surveillence/motion_postprocess.service /etc/systemd/system/motion_postprocess.service

sudo systemctl daemon-reload
sudo systemctl enable --now capture.service
sudo systemctl enable --now lores.service

# to stop and disable a service for testing:
# sudo systemctl stop motion_postprocess.service
# sudo systemctl disable motion_postprocess.service

echo "✅ Setup complete. Recording should start now and at boot."
