import os
import cv2
import numpy as np
import subprocess
import shutil
import logging
from pathlib import Path
import time

LOG_FILE = f"/home/piuser/videos/logs/motion_detect.log"

SLEEP_INTERVAL=2
PIXEL_THRESHOLD=10
CHANGE_RATIO=0.006
FLUSH_N_CLIPS = 3 # if you have more than this many clips in a row with motion, flush them out into another clip even if you'll cut up the motion. 

LQ_WIDTH, LQ_HEIGHT = 160, 90  # resize early in ffmpeg
 
MIN_FREE_SPACE = 2 * 1024 * 1024 * 1024  # 2 GB

IN_PROGRESS = "partial"
FINAL = "final"

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[
                        logging.FileHandler(LOG_FILE),
                        logging.StreamHandler()  # ensures output appears in journalctl/systemd logs
                    ])

logging.debug("test")

def ensure_space_for_video(new_video_path: Path, clip_dir):
    """If SD card is too full, delete the new video to prevent overflow."""
    try:
        stat = shutil.disk_usage(clip_dir)
        free_space = stat.free

        if free_space < MIN_FREE_SPACE:
            logging.warning(
                f"Low disk space ({free_space / (1024**2):.1f} MB free). Deleting {new_video_path.name}"
            )
            if new_video_path.exists():
                new_video_path.unlink()  # Delete the file
                logging.info(f"Deleted {new_video_path.name} to save space.")
            else:
                logging.warning(f"{new_video_path} not found; could not delete.")
            return False
        else:
            logging.debug(f"Enough space available ({free_space / (1024**2):.1f} MB free).")
            return True
        
    except Exception as e:
        logging.error(f"Error checking disk space: {e}")
        return False

def extract_sample_frames(input_path, tmp_dir):
    """Efficiently extract sample frames directly from .h264 via ffmpeg pipe."""
    logging.debug(f"Extracting sample frames (optimized) from {input_path}")
    vf_filter = f"scale={LQ_WIDTH}:{LQ_HEIGHT},format=yuv420p"
    output_pattern = os.path.join(tmp_dir, "frame_%04d.jpg")
    cmd = [
        "ffmpeg", "-hide_banner", 
        "-loglevel", "warning",
        "-skip_frame", "nokey", # efficiently extract just the keyframes
        "-i", input_path,
        "-vf", vf_filter,
        "-fps_mode", "vfr",
        "-q:v", "4",              # JPEG quality
        "-y", output_pattern
    ]

    # logging.debug(cmd)

    subprocess.run(cmd, check=True)

    # Read frames back into memory
    frames = []
    for file in os.listdir(tmp_dir):
        path = os.path.join(tmp_dir, file)
        frame = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if frame is not None:
            frames.append(frame)
        os.remove(path) #hopefully not a mistake?
    logging.debug(f"generated/read {len(frames)} frames")
    return frames

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
    
    # frames = [cv2.resize(f, (0,0), fx=0.25, fy=0.25) for f in frames] # no longer needed
    frames = [cv2.GaussianBlur(f, (7,7), 0) for f in frames]

    total_pixels = frames[0].size
    # logging.info(f"total pixels {total_pixels}")
    ratios = []

    for a, b in zip(frames, frames[1:]):
        diff = cv2.absdiff(a, b)
        motion_mask = diff > pixel_thresh
        ratio = np.count_nonzero(motion_mask) / total_pixels
        ratios.append(ratio)
    logging.info(f"ratios: {[f'{ratio:0.3f}, ' for ratio in ratios]}")
    ratios = [ratio for ratio in ratios if ratio < 0.90] # Remove noisy light issues?
    if len(ratios) == 0:
        return True # todo: this isn't the best way to handle all of this, but this handles the edge case if all of the ratios are extremely large. 
    logging.info(f"cleaned ratios: {[f'{ratio:0.3f}, ' for ratio in ratios]}")
    avg_ratio = np.mean(ratios)
    logging.info(f"motion pixel ratio: {avg_ratio:.6f}")
    return avg_ratio > change_ratio

# === Save clip ===
def save_clip(segments,  clip_dir, tmp_dir, additional_note=None,):
    """Concatenate motion segments into a single mp4 clip."""
    if not segments:
        return
    first_clip_number = os.path.basename(segments[0]).replace('segment_', '').replace('.h264','')
    clip_file_extension = ".mp4"
    clip_name = f"clip_{first_clip_number}"
    iter_num = 1 # doesn't overwrite files when the device resets.
    while (os.path.exists(os.path.join(clip_dir, clip_name+f"_{iter_num}"+clip_file_extension))):
        iter_num += 1
    clip_name = clip_name+f"_{iter_num}"
    if additional_note is not None:
        clip_name = clip_name + f"_{additional_note}"
    clip_name = clip_name+clip_file_extension
    clip_path = os.path.join(clip_dir, clip_name)

    try:
        with open(os.path.join(tmp_dir, "segments.txt"), "w") as f:
            for s in segments:
                f.write(f"file '{s}'\n")

        logging.info(f"Creating clip from {len(segments)} segments → {clip_path}")

        result = subprocess.run([
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", os.path.join(tmp_dir, "segments.txt"), "-c", "copy",
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


def clear_buffer_dir(buffer_dir, old_buffer_dir):
    logging.info("Removing segments")
    segments = os.listdir(buffer_dir)
    for segment in segments:
        if "segment_000000.h264" in segment or "segment_000001.h264" in segment:
            logging.info(f"Skipping segment {segment} for removal")
            continue #Skip the first currently-recorded videos. 
        else:
            logging.info(f"Removing segment {segment}")
            src = os.path.join(buffer_dir, segment)
            dest = os.path.join(old_buffer_dir, segment)
            os.rename(src, dest) # Note that this may overwrite some clips, this is currently acceptable choice. 


def run_motion_process_for_buffer(buffer_dir, clip_dir, tmp_dir):
    motion_group = []
    processed_segments = set()
    motion_run_continuation = False
    while True:
        try:
            segments = sorted(os.listdir(buffer_dir)) #assumes a sortable order
            # Skip already processed
            segments = [s for s in segments if s not in processed_segments]
            if not segments:
                logging.debug("No available segments to process, sleeping")
                time.sleep(SLEEP_INTERVAL)
                continue

            for i, seg in enumerate(segments):
                logging.debug(f"Processing segment #{i}, {seg}")
                seg_path = os.path.join(buffer_dir, seg)
                # Always skip last one (may still be writing)
                if i == (len(segments) - 1):
                    logging.debug("Reached the end of the segments")
                    time.sleep(SLEEP_INTERVAL)
                    break

                if not ensure_space_for_video(Path(seg_path), clip_dir=clip_dir):
                    logging.warning("Not enough space, new file deleted")
                    time.sleep(SLEEP_INTERVAL)
                    break

                frames = extract_sample_frames(seg_path, tmp_dir=tmp_dir)
                motion = detect_motion(frames)
                if motion:
                    logging.debug(f"Adding segment #{i}, {seg} to the motion group")
                    motion_group.append(seg_path)
                    if len(motion_group) > FLUSH_N_CLIPS:
                        logging.debug(f"Flushing all current motion group segments to a clip despite motion being detected")
                        motion_group_to_save = motion_group[:-1]
                        save_clip(motion_group_to_save, clip_dir=clip_dir, tmp_dir=tmp_dir, additional_note=IN_PROGRESS)
                        motion_group = [motion_group[-1]] # motion_group = [seg_path] #note that this prioritizes cohesive video viewing over later recompilation into one big video. Think about changing later todo
                        motion_run_continuation = True
                else:
                    logging.debug(f"Saving all current motion group segments to a clip")
                    if motion_run_continuation:
                        save_clip(motion_group, clip_dir=clip_dir, tmp_dir=tmp_dir, additional_note=FINAL)
                    else:
                        save_clip(motion_group, clip_dir=clip_dir, tmp_dir=tmp_dir)
                    motion_group = []
                    os.remove(seg_path)
                    logging.debug(f"Removed non-motion segment: {seg_path}")
                    motion_run_continuation = False
                
                processed_segments.add(seg)
                time.sleep(0.3)
            first_run = False
            time.sleep(SLEEP_INTERVAL)

        except Exception as e:
            logging.exception(f"Main loop error: {e}")
            time.sleep(SLEEP_INTERVAL)
