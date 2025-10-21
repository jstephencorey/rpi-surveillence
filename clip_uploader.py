import os
import time
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

WATCH_DIR = "/home/piuser/videos/clips"
SERVER_URL = "http://your.server.address:5000/upload_clip"  # change to your Flask endpoint

class ClipUploadHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".mp4"):
            file_path = event.src_path
            print(f"[INFO] New clip detected: {file_path}")
            self.upload_clip(file_path)

    def upload_clip(self, file_path):
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f, "video/mp4")}
                print(f"[INFO] Uploading {file_path} ...")
                response = requests.post(SERVER_URL, files=files, timeout=60)
                if response.status_code == 200:
                    print(f"[SUCCESS] Uploaded {file_path}")
                else:
                    print(f"[ERROR] Failed to upload {file_path}: {response.status_code} {response.text}")
        except Exception as e:
            print(f"[EXCEPTION] {e}")

def main():
    event_handler = ClipUploadHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=False)
    observer.start()
    print(f"[INFO] Watching directory: {WATCH_DIR}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
