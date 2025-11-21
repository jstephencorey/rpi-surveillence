#!/bin/bash
set -e

echo "Stopping/disabling old services..." #todo remove this eventually #todo deal with this on the first run?
# Function to check if a service exists
service_exists() {
    systemctl list-unit-files "$1" &>/dev/null
    return $?
}

# Stop and disable services if they exist
if service_exists "capture_local.service"; then
    sudo systemctl stop capture_local.service
    sudo systemctl disable capture_local.service
fi

if service_exists "capture_upload.service"; then
    sudo systemctl stop capture_upload.service
    sudo systemctl disable capture_upload.service
fi

if service_exists "motion_postprocess_local.service"; then
    sudo systemctl stop motion_postprocess_local.service
    sudo systemctl disable motion_postprocess_local.service
fi

if service_exists "motion_postprocess_upload.service"; then
    sudo systemctl stop motion_postprocess_upload.service
    sudo systemctl disable motion_postprocess_upload.service
fi

if service_exists "clip_uploader.service"; then
    sudo systemctl stop clip_uploader.service
    sudo systemctl disable clip_uploader.service
fi
echo "Done shutting down old services"