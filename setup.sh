#!/bin/bash
set -e

VIDEOS_DIR="/home/piuser/videos"

echo "Creating video directories..."
mkdir -p -m 755 "$VIDEOS_DIR/buffer" "$VIDEOS_DIR/clips"

echo "Installing motion config..."
sudo apt install -y motion ffmpeg
sudo cp motion.conf /etc/motion/motion.conf
sudo systemctl enable motion

echo "Installing services..."
sudo cp camera.service /etc/systemd/system/camera.service
sudo cp lowres_stream.service /etc/systemd/system/lowres_stream.service
sudo systemctl daemon-reload
sudo systemctl enable camera.service lowres_stream.service
sudo systemctl start lowres_stream.service camera.service

echo "✅ Setup complete. Recording should start at boot."
