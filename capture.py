#!/usr/bin/env python3
import subprocess
import os
import signal
import logging

BUFFER_DIR = "/home/piuser/videos/buffer"
LOG_FILE = "/home/piuser/videos/logs/capture.log"

HQ_WIDTH = "1920"
HQ_HEIGHT = "1080"
HQ_FRAMERATE = "30"
_SECS_PER_SEGMENT = 10 # N seconds
HQ_SEGMENT = str(_SECS_PER_SEGMENT*1000) # in milliseconds

os.makedirs(BUFFER_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(filename=LOG_FILE,
                    level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    logging.info("Starting capture loop...")
    segment_pattern = os.path.join(BUFFER_DIR, "segment_%05d.h264")

    cmd = [
        "rpicam-vid",
        "--inline",
        "--width", HQ_WIDTH,
        "--height", HQ_HEIGHT,
        "--framerate", HQ_FRAMERATE,
        "--segment", HQ_SEGMENT,  # milliseconds per file
        "--output", segment_pattern,
        "--timeout", "0",  # run indefinitely
        "--codec", "h264"
    ]

    process = subprocess.Popen(cmd)
    logging.info(f"Started rpicam-vid with PID {process.pid}")

    # Handle clean shutdown
    def shutdown(sig, frame):
        logging.info("Received stop signal, terminating capture...")
        process.terminate()
        process.wait()
        logging.info("Capture stopped cleanly.")

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    process.wait()

if __name__ == "__main__":
    main()
