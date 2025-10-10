#!/bin/bash
VIDEOS_DIR="/home/piuser/videos"
BUFFER_DIR="$VIDEOS_DIR/buffer"
CLIP_DIR="$VIDEOS_DIR/clips"
SEGMENT_LENGTH=10
MAX_SEGMENTS=60

mkdir -p "$BUFFER_DIR" "$CLIP_DIR"

# Start high-res recording
rpicam-vid -t 0 --inline --segment $((SEGMENT_LENGTH*1000)) \
  -o "$BUFFER_DIR/segment_%05d.h264" \
  --width 1920 --height 1080 --framerate 30 --codec h264 &
VID_PID=$!
echo "Started rpicam-vid PID $VID_PID"

while true; do
  sleep 2

  # Maintain ring buffer
  ls -1tr $BUFFER_DIR/*.h264 2>/dev/null | head -n -$MAX_SEGMENTS | xargs -r rm

  # Motion detected?
  if [ -f /tmp/motion.flag ]; then
    echo "Motion detected!"

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    OUTPUT="$CLIP_DIR/clip_$TIMESTAMP.mp4"

    # Grab last 12 segments (≈2 min)
    ls -1tr $BUFFER_DIR/*.h264 | tail -n 12 > /tmp/segments.txt
    ffmpeg -f concat -safe 0 -i <(for f in $(cat /tmp/segments.txt); do echo "file '$f'"; done) \
           -c copy "$OUTPUT" -y

    echo "Saved clip: $OUTPUT"
  fi
done
