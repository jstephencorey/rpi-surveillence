import os
import time
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

# === CONFIG ===
WATCH_DIR = "/home/piuser/videos/clips"
SERVER_URL = "http://192.168.0.61:5000/upload_clip"
SLEEP_INTERVAL = 2  # seconds
STABILITY_CHECK_TIME = 5  # seconds to wait to confirm file size unchanged

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

load_dotenv()


def file_is_stable(file_path: Path) -> bool:
    """Check if file size stays the same over a short period (not still being written)."""
    size1 = file_path.stat().st_size
    time.sleep(STABILITY_CHECK_TIME)
    size2 = file_path.stat().st_size
    return size1 == size2


def upload_clip(file_path: Path):
    """Upload a completed clip to the server."""
    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "video/mp4")}
            logging.info(f"Uploading {file_path.name} ...")
            response = requests.post(SERVER_URL, files=files, timeout=60)
        if response.status_code == 200:
            logging.info(f"✅ Uploaded {file_path.name}")
            file_path.unlink(missing_ok=True)
        else:
            logging.error(f"❌ Upload failed ({response.status_code}): {response.text}")
    except Exception as e:
        logging.exception(f"Upload exception: {e}")


def main():
    processed_files = set()
    first_run = True

    logging.info(f"Watching directory: {WATCH_DIR}")

    while True:
        try:
            files = sorted(
                f for f in os.listdir(WATCH_DIR) if f.lower().endswith(".mp4")
            )
            files = [f for f in files if f not in processed_files]

            if not files:
                time.sleep(SLEEP_INTERVAL)
                continue

            for i, filename in enumerate(files):
                file_path = Path(WATCH_DIR) / filename

                if not file_path.exists():
                    continue

                # Check stability before uploading
                if not file_is_stable(file_path):
                    logging.debug(f"File {file_path.name} still being written, skipping.")
                    time.sleep(0.1)
                    continue

                # Upload
                upload_clip(file_path)

                if not first_run:
                    processed_files.add(filename)

                time.sleep(0.2)

            first_run = False
            time.sleep(SLEEP_INTERVAL)

        except Exception as e:
            logging.exception(f"Main loop error: {e}")
            time.sleep(SLEEP_INTERVAL)


if __name__ == "__main__":
    main()
