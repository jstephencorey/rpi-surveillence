#!/bin/bash
set -e

TARGET_DIRECTORY="/mnt/external_drive"
VIDEOS_DIR="$TARGET_DIRECTORY/videos"

echo "Running setup for saving videos locally, to an external drive"

echo "Creating video directories in $VIDEOS_DIR..."
mkdir -p -m 755 "$VIDEOS_DIR/buffer" "$VIDEOS_DIR/clips"
sudo chown -R piuser:piuser $VIDEOS_DIR

echo "Installing ffmpeg and python libraries..."
sudo apt install -y ffmpeg python3-opencv python3-numpy python3-dotenv

echo "Stopping/disabling old services via shutdown_services.sh"
sudo ./shutdown_services.sh
echo "Done shutting down services via shutdown_services.sh"

echo "Installing systemd services..."
sudo cp /home/piuser/rpi-surveillence/capture_local.service /etc/systemd/system/capture_local.service
sudo cp /home/piuser/rpi-surveillence/motion_postprocess_local.service /etc/systemd/system/motion_postprocess_local.service

sudo systemctl daemon-reload
sudo systemctl enable --now capture_local.service
sudo systemctl enable --now motion_postprocess_local.service

echo "✅ Setup complete. Recording should start now and at boot."
