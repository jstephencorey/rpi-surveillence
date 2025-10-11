import cv2
import os
import time
import numpy as np
import subprocess

BUFFER_DIR = "/home/piuser/videos/buffer"
CLIP_DIR = "/home/piuser/videos/clips"
MOTION_THRESHOLD = 3000    # fewer pixels triggers motion, tune this
FRAME_SKIP = 3             # process every 3rd frame
DOWNSAMPLE_WIDTH = 320
DOWNSAMPLE_HEIGHT = 240

os.makedirs(CLIP_DIR, exist_ok=True)

motion_group = []
processed_segments = set()

def detect_motion(video_path):
    cap = cv2.VideoCapture(video_path)
    ret, prev_frame = cap.read()
    if not ret:
        cap.release()
        return False
    # Downsample
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
        if cv2.countNonZero(thresh) > MOTION_THRESHOLD:
            motion_detected = True
            break
        prev_gray = gray

    cap.release()
    return motion_detected

def save_clip(segments):
    if not segments:
        return
    clip_name = f"clip_{os.path.basename(segments[0]).replace('segment_', '').replace('.h264','')}.mp4"
    clip_path = os.path.join(CLIP_DIR, clip_name)
    with open("/tmp/segments.txt", "w") as f:
        for s in segments:
            f.write(f"file '{s}'\n")
    subprocess.run([
        "ffmpeg", "-f", "concat", "-safe", "0",
        "-i", "/tmp/segments.txt", "-c", "copy",
        clip_path, "-y"
    ])
    print(f"Saved clip: {clip_path}")
    for s in segments:
        os.remove(s)

# --- Main loop ---
while True:
    segments = sorted(os.listdir(BUFFER_DIR))
    # Skip already processed segments
    segments = [s for s in segments if s not in processed_segments]

    for i, seg in enumerate(segments):
        seg_path = os.path.join(BUFFER_DIR, seg)
        # Always leave the last segment unprocessed to "lookahead"
        if i == len(segments) - 1:
            break

        motion = detect_motion(seg_path)
        if motion:
            motion_group.append(seg_path)
        else:
            if motion_group:
                save_clip(motion_group)
                motion_group = []
            os.remove(seg_path)

        processed_segments.add(seg)

    time.sleep(2)
