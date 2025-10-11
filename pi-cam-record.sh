#!/bin/bash
VIDEOS_DIR="/home/piuser/videos"
BUFFER_DIR="$VIDEOS_DIR/buffer"
SEGMENT_LENGTH=10

mkdir -p "$BUFFER_DIR"

# Start high-res recording
rpicam-vid -t 0 --inline --segment $((SEGMENT_LENGTH*1000)) \
  -o "$BUFFER_DIR/segment_%05d.h264" \
  --width 1920 --height 1080 --framerate 30 --codec h264
