#!/usr/bin/env python3
import subprocess
import os
import signal
import logging
import time

TARGET_DIR = os.getenv('TARGET_DIRECTORY', '/home/piuser')
BUFFER_DIR = f"{TARGET_DIR}/videos/buffer"
LOG_FILE = "/home/piuser/videos/logs/capture.log"

HQ_WIDTH = "1920"
HQ_HEIGHT = "1080"
HQ_FRAMERATE = 30


_I_FRAME_EVERY = 3
HQ_INTRA = HQ_FRAMERATE * _I_FRAME_EVERY # record an I-frame every _I_FRAME_EVERY seconds, used for fast decoding of frames for ffmpeg to later extract. (the only way I could get speedup > 1) 
_SECS_PER_SEGMENT = 20 # N seconds
HQ_SEGMENT = str(_SECS_PER_SEGMENT*1000) # in milliseconds

INITIAL_PAUSE_SECS = 10 # (wait to clear the buffer dir, start up everything, etc. )

os.makedirs(BUFFER_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[
                        logging.FileHandler(LOG_FILE),
                        logging.StreamHandler()  # ensures output appears in journalctl/systemd logs
                    ])

def main():
    logging.info(f"Pausing for {INITIAL_PAUSE_SECS} secs to let things set up")
    time.sleep(INITIAL_PAUSE_SECS)
    logging.info("Starting capture loop...")
    segment_pattern = os.path.join(BUFFER_DIR, "segment_%06d.h264")
    logging.debug(f"writing the output to {BUFFER_DIR}")

    cmd = [
        "rpicam-vid",
        "--inline",
        "--width", HQ_WIDTH,
        "--height", HQ_HEIGHT,
        "--framerate", str(HQ_FRAMERATE),
        "--segment", HQ_SEGMENT,  # milliseconds per file
        "--output", segment_pattern,
        "--intra", str(HQ_INTRA),
        "--timeout", "0",  # run indefinitely
        "--codec", "h264",
        "--nopreview",
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
