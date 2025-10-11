#!/bin/bash
set -e

VIDEOS_DIR="/home/piuser/videos"

echo "Creating video directories..."
mkdir -p -m 755 "$VIDEOS_DIR/buffer" "$VIDEOS_DIR/clips"
sudo chown -R piuser:piuser /home/piuser/videos
mkfifo /tmp/motion.mjpeg
sudo chown -R piuser:piuser /tmp/motion.mjpeg

echo "Installing motion config..."
sudo apt install -y motion ffmpeg
sudo cp motion.conf /etc/motion/motion.conf
sudo systemctl enable motion

echo "Installing services..."
sudo cp camera.service /etc/systemd/system/camera.service
sudo systemctl daemon-reload
sudo systemctl start lowres_stream.service camera.service

echo "✅ Setup complete. Recording should start at boot."
