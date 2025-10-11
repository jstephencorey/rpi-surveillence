#!/bin/bash
set -e

VIDEOS_DIR="/home/piuser/videos"

echo "Creating video directories..."
mkdir -p -m 755 "$VIDEOS_DIR/buffer" "$VIDEOS_DIR/clips"
sudo chown -R piuser:piuser /home/piuser/videos

echo "Installing stuff..."
sudo apt install -y ffmpeg python3-pip

echo "Installing Python dependencies..."
sudo pip3 install -r /home/piuser/rpi-surveillence/requirements.txt

echo "Installing systemd services..."
sudo cp /home/piuser/rpi-surveillence/camera.service /etc/systemd/system/camera.service
sudo cp /home/piuser/rpi-surveillence/motion_postprocess.service /etc/systemd/system/motion_postprocess.service

sudo systemctl daemon-reload
sudo systemctl enable --now camera.service
sudo systemctl enable --now motion_postprocess.service

echo "✅ Setup complete. Recording should start now and at boot."
