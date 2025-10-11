#!/bin/bash
VIDEOS_DIR="/home/piuser/videos"
BUFFER_DIR="$VIDEOS_DIR/buffer"
CLIP_DIR="$VIDEOS_DIR/clips"
SEGMENT_LENGTH=5
MAX_SEGMENTS=30

mkdir -p "$BUFFER_DIR" "$CLIP_DIR"

# Start high-res rpicam
rpicam-vid -t 0 --inline \
  --segment $((SEGMENT_LENGTH*1000)) \
  -o "$BUFFER_DIR/segment_%05d.h264" \
  --width 1920 --height 1080 --framerate 30 --codec h264 \
  --lores-width 320 --lores-height 240 --lores-fps 5 \
  --codec lores mjpeg --lores-output /tmp/motion.mjpeg &
VID_PID=$!
echo "Started rpicam-vid PID $VID_PID"

# Start motion detection
motion -c /etc/motion/motion.conf &
MOTION_PID=$!
echo "Started motion PID $MOTION_PID"

# Main loop
while true; do
  sleep 2

  # Maintain ring buffer
  ls -1tr $BUFFER_DIR/*.h264 2>/dev/null | head -n -$MAX_SEGMENTS | xargs -r rm

  # Motion detected?
  if [ -f /tmp/motion.flag ]; then
    echo "Motion detected!"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    OUTPUT="$CLIP_DIR/clip_$TIMESTAMP.mp4"

    ls -1tr $BUFFER_DIR/*.h264 | tail -n 12 > /tmp/segments.txt
    ffmpeg -f concat -safe 0 -i <(for f in $(cat /tmp/segments.txt); do echo "file '$f'"; done) \
           -c copy "$OUTPUT" -y

    echo "Saved clip: $OUTPUT"
  fi
done
