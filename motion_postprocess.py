import cv2
import os
import time
import numpy as np
import subprocess
import logging
from datetime import datetime

# === Configuration ===
BUFFER_DIR = "/home/piuser/videos/buffer"
CLIP_DIR = "/home/piuser/videos/clips"
LOG_PATH = "/home/piuser/videos/processor.log"

MOTION_THRESHOLD = 3000    # tune based on environment
FRAME_SKIP = 3             # process every Nth frame
DOWNSAMPLE_WIDTH = 320
DOWNSAMPLE_HEIGHT = 240
SLEEP_INTERVAL = 2         # seconds between directory scans

# === Logging Setup ===
os.makedirs(CLIP_DIR, exist_ok=True)
os.makedirs(BUFFER_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()  # ensures output appears in journalctl/systemd logs
    ]
)

logger = logging.getLogger("motion-processor")

motion_group = []
processed_segments = set()

# === Motion Detection ===
def detect_motion(video_path):
    """Return True if motion is detected in the given video segment."""
    cap = cv2.VideoCapture(video_path)
    ret, prev_frame = cap.read()
    if not ret:
        logger.warning(f"Failed to read first frame from {video_path}")
        cap.release()
        return False

    prev_frame = cv2.resize(prev_frame, (DOWNSAMPLE_WIDTH, DOWNSAMPLE_HEIGHT))
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    prev_gray = cv2.GaussianBlur(prev_gray, (21, 21), 0)

    frame_index = 0
    motion_detected = False

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_index += 1
        if frame_index % FRAME_SKIP != 0:
            continue

        frame = cv2.resize(frame, (DOWNSAMPLE_WIDTH, DOWNSAMPLE_HEIGHT))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        diff = cv2.absdiff(prev_gray, gray)
        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
        motion_pixels = cv2.countNonZero(thresh)

        if motion_pixels > MOTION_THRESHOLD:
            logger.info(f"Motion detected in {os.path.basename(video_path)} ({motion_pixels} changed pixels)")
            motion_detected = True
            break

        prev_gray = gray

    cap.release()
    return motion_detected


# === Save clip ===
def save_clip(segments):
    """Concatenate motion segments into a single mp4 clip."""
    if not segments:
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clip_name = f"clip_{timestamp}.mp4"
    clip_path = os.path.join(CLIP_DIR, clip_name)

    try:
        with open("/tmp/segments.txt", "w") as f:
            for s in segments:
                f.write(f"file '{s}'\n")

        logger.info(f"Creating clip from {len(segments)} segments → {clip_path}")

        result = subprocess.run([
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", "/tmp/segments.txt", "-c", "copy",
            clip_path, "-y"
        ], capture_output=True, text=True)

        if result.returncode == 0:
            logger.info(f"✅ Saved clip: {clip_path}")
            for s in segments:
                os.remove(s)
                logger.debug(f"Deleted processed segment: {s}")
        else:
            logger.error(f"FFmpeg failed: {result.stderr}")

    except Exception as e:
        logger.exception(f"Error while saving clip: {e}")


# === Main Loop ===
logger.info("Starting motion processor loop...")
while True:
    try:
        segments = sorted(os.listdir(BUFFER_DIR))
        # Skip already processed
        segments = [s for s in segments if s not in processed_segments]
        if not segments:
            time.sleep(SLEEP_INTERVAL)
            continue

        for i, seg in enumerate(segments):
            seg_path = os.path.join(BUFFER_DIR, seg)
            # Always skip last one (may still be writing)
            if i == len(segments) - 1:
                break

            motion = detect_motion(seg_path)
            if motion:
                motion_group.append(seg_path)
            else:
                if motion_group:
                    save_clip(motion_group)
                    motion_group = []
                else:
                    os.remove(seg_path)
                    logger.debug(f"Removed non-motion segment: {seg_path}")

            processed_segments.add(seg)

    except Exception as e:
        logger.exception(f"Main loop error: {e}")
        time.sleep(SLEEP_INTERVAL)
