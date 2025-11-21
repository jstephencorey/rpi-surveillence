import os
from capture_lib import capture_to_buffer

BUFFER_DIR = f"/home/piuser/videos/buffer"

os.makedirs(BUFFER_DIR, exist_ok=True)

def main():
    capture_to_buffer(BUFFER_DIR)

if __name__ == "__main__":
    main()