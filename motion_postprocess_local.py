import os
from motion_postprocess_lib import clear_buffer_dir, run_motion_process_for_buffer

TARGET_DIR = "/mnt/external_drive"
BUFFER_DIR = f"{TARGET_DIR}/videos/buffer"
OLD_BUFFER_DIR = f"{TARGET_DIR}/videos/buffer_old"
TMP_DIR = f"{TARGET_DIR}/videos/tmp"
CLIP_DIR = f"{TARGET_DIR}/videos/clips"

os.makedirs(CLIP_DIR, exist_ok=True)
os.makedirs(BUFFER_DIR, exist_ok=True)
os.makedirs(OLD_BUFFER_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)


if __name__ == "__main__":
    clear_buffer_dir(buffer_dir=BUFFER_DIR,
                     old_buffer_dir=OLD_BUFFER_DIR)
    run_motion_process_for_buffer(buffer_dir=BUFFER_DIR,
                                  clip_dir=CLIP_DIR,
                                  tmp_dir=TMP_DIR)