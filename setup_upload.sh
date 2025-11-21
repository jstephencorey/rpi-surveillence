#!/bin/bash
set -e

TARGET_DIRECTORY="/home/piuser"
VIDEOS_DIR="$TARGET_DIRECTORY/videos"

echo "Running setup for uploading surveillence videos to my server"

echo "Creating video directories in $VIDEOS_DIR..."
mkdir -p -m 755 "$VIDEOS_DIR/buffer" "$VIDEOS_DIR/clips"
sudo chown -R piuser:piuser $VIDEOS_DIR

echo "Installing ffmpeg and python libraries..."
sudo apt install -y ffmpeg python3-opencv python3-numpy python3-dotenv

echo "Stopping/disabling old services via shutdown_services.sh"
sudo ./shutdown_services.sh
echo "Done shutting down services via shutdown_services.sh"

echo "Installing systemd services..."
sudo cp /home/piuser/rpi-surveillence/capture_upload.service /etc/systemd/system/capture_upload.service
sudo cp /home/piuser/rpi-surveillence/motion_postprocess_upload.service /etc/systemd/system/motion_postprocess_upload.service
sudo cp /home/piuser/rpi-surveillence/clip_uploader.service /etc/systemd/system/clip_uploader.service

sudo systemctl daemon-reload
sudo systemctl enable --now capture_upload.service
sudo systemctl enable --now motion_postprocess_upload.service
sudo systemctl enable --now clip_uploader.service

echo "✅ Setup complete. Recording should start now and at boot."
