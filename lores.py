#!/usr/bin/env python3
import os
import time
import subprocess
import logging
import shutil

BUFFER_DIR = "/home/piuser/videos/buffer"
CLIP_DIR = "/home/piuser/videos/clips"
LOG_FILE = "/home/piuser/videos/logs/postprocess.log"

LQ_WIDTH = 640
LQ_HEIGHT = 360
LQ_FPS = 5

os.makedirs(CLIP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(filename=LOG_FILE,
                    level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

def process_file(file_path):
    base = os.path.basename(file_path)
    name, _ = os.path.splitext(base)
    output_hq = os.path.join(CLIP_DIR, base)
    output_lores = os.path.join(CLIP_DIR, f"{name}_lores.mp4")

    # Move the original segment into clips
    shutil.move(file_path, output_hq)
    logging.info(f"Moved {base} to clips directory.")

    # Generate lores version
    cmd = [
        "ffmpeg", "-y",
        "-i", output_hq,
        "-vf", f"scale={LQ_WIDTH}:{LQ_HEIGHT},fps={LQ_FPS}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "32", #32 means low quality, which is fine for this.
        output_lores
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        logging.info(f"Generated lores version for {base}")
    except subprocess.CalledProcessError:
        logging.error(f"ffmpeg failed for {base}")

def main():
    logging.info("Starting postprocess watcher...")
    processed = set()

    while True:
        for file in os.listdir(BUFFER_DIR):
            if not file.endswith(".h264"):
                continue
            full_path = os.path.join(BUFFER_DIR, file)
            if file in processed:
                continue

            # Ensure file is stable (not still being written)
            size1 = os.path.getsize(full_path)
            time.sleep(2)
            size2 = os.path.getsize(full_path)
            if size1 == size2:
                process_file(full_path)
                processed.add(file)

        time.sleep(5)

if __name__ == "__main__":
    main()
