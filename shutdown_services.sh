#!/bin/bash
set -e

echo "Stopping/disabling old services..." #todo remove this eventually #todo deal with this on the first run?
sudo systemctl disable capture.service
sudo systemctl stop capture.service
sudo systemctl disable motion_postprocess.service
sudo systemctl stop motion_postprocess.service
sudo systemctl disable clip_uploader.service
sudo systemctl stop clip_uploader.service
echo "Done shutting down old services"