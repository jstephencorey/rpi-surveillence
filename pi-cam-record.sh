#!/bin/bash
VIDEOS_DIR="/home/piuser/videos/buffer"
SEGMENT_LENGTH=10  # seconds

mkdir -p "$VIDEOS_DIR"

rpicam-vid -t 0 --inline \
  --segment $((SEGMENT_LENGTH*1000)) \
  -o "$VIDEOS_DIR/segment_%06d.h264" \
  --width 1920 --height 1080 --framerate 30 --codec h264
