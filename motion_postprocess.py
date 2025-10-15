import os
import cv2
import numpy as np
import subprocess
import tempfile
import logging
import time

# BUFFER_DIR = "/home/piuser/videos/buffer"
BUFFER_DIR = "./buffer/buffer_test"
BUFFER_DIR = "S:\\Dev\\rpi-surveillence\\buffer\\buffer_test"
TMP_DIR = "./buffer/buffer_tmp"
# BUFFER_DIR = "./buffer"
# LOG_FILE = "/home/piuser/videos/logs/motion_detect.log"
FRAMES_TO_SAMPLE = 5
SLEEP_INTERVAL=2
PIXEL_THRESHOLD=10
CHANGE_RATIO=0.001
FLUSH_N_CLIPS = 32 # if you have more than this many clips in a row with motion, flush them out into another clip even if you'll cut up the motion. 

CLIP_DURATION = 10.0
CLIP_FPS = 30
CLIP_FRAME_SPEED = 0.0339

LQ_WIDTH, LQ_HEIGHT = 160, 90  # resize early in ffmpeg

# CLIP_DIR = "/buffer/clips_test"
CLIP_DIR = "S:\\Dev\\rpi-surveillence\\buffer\\clips_test"
os.makedirs(CLIP_DIR, exist_ok=True)
os.makedirs(BUFFER_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)
# os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[
                        # logging.FileHandler(LOG_FILE),
                        logging.StreamHandler()  # ensures output appears in journalctl/systemd logs
                    ])
logging.debug("test")
# def extract_sample_frames(input_path):
#     """Rewrap .h264 to .mp4 and extract 5 sample frames as np.array list."""
#     with tempfile.TemporaryDirectory() as tmpdir:
#         logging.debug("extracting sample frames")
#         temp_mp4 = os.path.join(tmpdir, "temp.mp4")

#         # Step 1: Rewrap to MP4 (no re-encode)
#         cmd_wrap = ["ffmpeg", "-hide_banner", "-loglevel", "error",
#                     "-f", "h264", "-i", input_path, "-c", "copy", "-y", temp_mp4]
#         subprocess.run(cmd_wrap, check=True)

#         # Step 2: Determine duration (seconds)
#         result = subprocess.run(
#             ["ffprobe", "-v", "error", "-show_entries", "format=duration",
#              "-of", "default=noprint_wrappers=1:nokey=1", temp_mp4],
#             capture_output=True, text=True
#         )
#         try:
#             duration = float(result.stdout.strip())
#         except ValueError:
#             logging.warning(f"Could not read duration for {input_path}")
#             return []

#         # Step 3: Extract sample frames
#         sample_times = np.linspace(0, duration, FRAMES_TO_SAMPLE, endpoint=False)
#         frames = []

#         for i, t in enumerate(sample_times):
#             frame_path = os.path.join(tmpdir, f"frame_{i}.jpg")
#             cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error",
#                    "-ss", str(t), "-i", temp_mp4, "-frames:v", "1",
#                    "-q:v", "4", "-y", frame_path]
#             subprocess.run(cmd, check=True)

#             frame = cv2.imread(frame_path, cv2.IMREAD_GRAYSCALE)
#             if frame is not None:
#                 frames.append(frame)

#         return frames

def extract_sample_frames(input_path):
    """Efficiently extract sample frames directly from .h264 via ffmpeg pipe."""
    logging.debug(f"Extracting sample frames (optimized) from {input_path}")
    with tempfile.TemporaryDirectory() as tmpdir:
    # tmpdir = "S:\\Dev\\rpi-surveillence\\buffer\\buffer_tmp"


        # Build select filter to pick N evenly spaced times
        select_expr = "+".join([
            f"gte(t,{t:.4f})*lt(t,{t+CLIP_FRAME_SPEED:.4f})"
            for t in np.linspace(0, CLIP_DURATION, FRAMES_TO_SAMPLE, endpoint=False)
        ])
        vf_filter = f"select='{select_expr}',scale={LQ_WIDTH}:{LQ_HEIGHT},format=gray"

        output_pattern = os.path.join(tmpdir, "frame_%03d.jpg")
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", input_path,
            "-vf", vf_filter,
            "-vsync", "vfr",
            "-q:v", "4",              # JPEG quality
            "-y", output_pattern
        ]

        # logging.debug(cmd)

        subprocess.run(cmd, check=True)

        # Read frames back into memory
        frames = []
        for i in range(FRAMES_TO_SAMPLE):
            path = os.path.join(tmpdir, f"frame_{i+1:03d}.jpg")  # ffmpeg starts at 1
            if not os.path.exists(path):
                continue
            frame = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if frame is not None:
                frames.append(frame)

        return frames

len(extract_sample_frames("S:\\Dev\\rpi-surveillence\\buffer\\buffer_test2\\segment_00021.h264"))
# def detect_motion(frames): # keeping this here for reference
#     """Return True if frame-to-frame difference exceeds threshold."""
#     # logging.debug("detecting motion")
#     if len(frames) < 2:
#         return False

#     frames = [cv2.GaussianBlur(cv2.resize(f, (0,0), fx=0.25, fy=0.25), (5,5), 0) for f in frames]

#     diffs = []
#     for a, b in zip(frames, frames[1:]):
#         diff = cv2.absdiff(a, b)
#         diffs.append(np.sum(diff))
#     avg_diff = np.mean(diffs)
#     logging.info(f"motion diff: {avg_diff:,}")
#     return avg_diff > MOTION_THRESHOLD

def detect_motion(frames, pixel_thresh=PIXEL_THRESHOLD, change_ratio=CHANGE_RATIO):
    """
    Detect motion based on % of pixels with large changes between frames.
    pixel_thresh: difference value (0–255) for pixel to count as 'changed'
    change_ratio: fraction of changed pixels needed to trigger motion
    """
    logging.debug("detecting motion on frames")
    if len(frames) < 2:
        logging.warning(f"not enough frames, only {len(frames)} of them")
        return False
    
    # frames = [cv2.resize(f, (0,0), fx=0.25, fy=0.25) for f in frames]
    frames = [cv2.GaussianBlur(f, (5,5), 0) for f in frames]

    total_pixels = frames[0].size
    ratios = []

    for a, b in zip(frames, frames[1:]):
        diff = cv2.absdiff(a, b)
        motion_mask = diff > pixel_thresh
        ratio = np.count_nonzero(motion_mask) / total_pixels
        ratios.append(ratio)

    avg_ratio = np.mean(ratios)
    logging.info(f"motion pixel ratio: {avg_ratio:.6f}")
    return avg_ratio > change_ratio
# def process_file(file_path):
#     base = os.path.basename(file_path)
#     # logging.info(f"Processing {base}")

#     try:
#         frames = extract_sample_frames(file_path)
#         if not frames:
#             logging.warning(f"No frames extracted from {base}")
#             return

#         if detect_motion(frames):
#             logging.info(f"Motion detected in {base}")
#             pass
#         else:
#             logging.info(f"No motion in {base}")
#     except subprocess.CalledProcessError:
#         logging.error(f"FFmpeg failed on {base}")
#     except Exception as e:
#         logging.exception(f"Error processing {base}: {e}")

# for i,filename in enumerate(sorted(os.listdir(BUFFER_DIR))):
#     if filename.lower().endswith(".h264"):
#         path = os.path.join(BUFFER_DIR, filename)
#         logging.info(path)
#         process_file(path)
#     if i > 20:
#         break

# === Save clip ===
def save_clip(segments):
    """Concatenate motion segments into a single mp4 clip."""
    if not segments:
        return
    first_clip_number = os.path.basename(segments[0]).replace('segment_', '').replace('.h264','')
    clip_file_extension = ".mp4"
    clip_name = f"clip_{first_clip_number}"
    iter_num = 1 # doesn't overwrite files when the device resets.
    while (os.path.exists(os.path.join(CLIP_DIR, clip_name+f"_{iter_num}"+clip_file_extension))):
        iter_num += 1
    clip_name = clip_name+f"_{iter_num}"+clip_file_extension
    clip_path = os.path.join(CLIP_DIR, clip_name)

    try:
        with open(os.path.join(TMP_DIR, "segments.txt"), "w") as f:
            for s in segments:
                f.write(f"file '{s}'\n")

        logging.info(f"Creating clip from {len(segments)} segments → {clip_path}")

        result = subprocess.run([
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", os.path.join(TMP_DIR, "segments.txt"), "-c", "copy",
            clip_path, "-y"
        ], capture_output=True, text=True)

        if result.returncode == 0:
            logging.info(f"✅ Saved clip: {clip_path}")
            for s in segments:
                os.remove(s)
                logging.debug(f"Deleted processed segment: {s}")
        else:
            logging.error(f"FFmpeg failed: {result.stderr}")

    except Exception as e:
        logging.exception(f"Error while saving clip: {e}")



if __name__ == "__main__":
    motion_group = []
    processed_segments = set()
    while True:
        try:
            segments = sorted(os.listdir(BUFFER_DIR)) #assumes a sortable order
            # Skip already processed
            segments = [s for s in segments if s not in processed_segments]
            if not segments:
                logging.debug("no available segments to process, sleeping")
                time.sleep(SLEEP_INTERVAL)
                continue

            for i, seg in enumerate(segments):
                logging.debug(f"processing segment #{i}, {seg}")
                seg_path = os.path.join(BUFFER_DIR, seg)
                # Always skip last one (may still be writing)
                if i == len(segments) - 1:
                    logging.debug("reached the end of the segments")
                    time.sleep(0.1)
                    break

                frames = extract_sample_frames(seg_path)
                motion = detect_motion(frames)
                if motion:
                    logging.debug(f"Adding segment #{i}, {seg} to the motion group")
                    motion_group.append(seg_path)
                    if len(motion_group) > FLUSH_N_CLIPS:
                        logging.debug(f"Flushing all current motion group segments to a clip despite motion being detected")
                        save_clip(motion_group)
                        motion_group = [seg_path] #note that this prioritizes cohesive video viewing over later recompilation into one big video. Think about changing later todo
                else:
                    if motion_group:
                        logging.debug(f"saving all current motion group segments to a clip")
                        save_clip(motion_group)
                        motion_group = []
                    os.remove(seg_path)
                    logging.debug(f"Removed non-motion segment: {seg_path}")

                processed_segments.add(seg)
                time.sleep(0.1)
            time.sleep(SLEEP_INTERVAL)

        except Exception as e:
            logging.exception(f"Main loop error: {e}")
            time.sleep(SLEEP_INTERVAL)