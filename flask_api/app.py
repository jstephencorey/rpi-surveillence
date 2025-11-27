from flask import Flask, request, jsonify
import os, subprocess, shutil, logging
import requests
from dotenv import load_dotenv
from datetime import datetime
import pytz
import uuid
import threading
from zoneinfo import ZoneInfo
import re
import pytz

# Load environment variables
load_dotenv()

# Load secrets from .env
SECRET_KEY = os.getenv("SECRET_KEY")
IMMICH_API_KEY = os.getenv("IMMICH_API_KEY")
IMMICH_UPLOAD_URL = str(os.getenv("IMMICH_UPLOAD_URL"))

ENCODED_DIR = "/data/video/encoded"
INCOMING_DIR = "/data/video/incoming"

os.makedirs(INCOMING_DIR, exist_ok=True)
os.makedirs(ENCODED_DIR, exist_ok=True)

# Flask app setup
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # increase if needed, currently 2 GB

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)


def encode_in_background_av1(input_path, av1_output_path):
    """Run ffmpeg AV1 NVENC encode asynchronously."""
    logging.info("Running background encode now")
    print("Converting", input_path, "to", av1_output_path)
    assert not os.path.exists(av1_output_path)

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-hwaccel", "vaapi",
            "-hwaccel_device", "/dev/dri/renderD129",
            "-i", input_path,
            "-vf", "hqdn3d=3:3:6:6,format=nv12,hwupload",
            "-c:v", "av1_vaapi",
            "-global_quality", "30", # Found through testing to be a as low as I could reasonably go without loosing too much quality
            "-low_power", "0",
            "-profile:v", "0",
            "-c:a", "copy",
            av1_output_path
        ]

        result = subprocess.run(
            cmd,
            check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True
        )
        logging.debug(result.stdout)
        logging.debug(result.stderr)
        logging.info(f"Finished [ENCODED] {av1_output_path}")
        # os.remove(input_path) #todo do I need this?
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"[ERROR] FFmpeg failed for {input_path}")
        logging.error(f"Return code: {e.returncode}")
        logging.error("--- FFmpeg stdout ---" + e.stdout + "--- FFmpeg stderr ---" + e.stderr)


def get_time_from_filename(filename):
    tz = pytz.timezone(os.getenv("TIMEZONE", "America/Denver"))
    # Extract the first datetime-like part: YYYYMMDD_HHMMSS
    m = re.search(r"(\d{8})-(\d{6})", filename)
    date_part, time_part = m.group(1), m.group(2)

    # Parse into a datetime
    dt = datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")
    dt = tz.localize(dt)
    return dt.isoformat()


def get_video_info(video_filename):
    # output_file_name = f"{DEVICE_ID}_{timestampstr}_{clip_id}_{additional_note}_{motion_group_id}.mp4"
    # Save incoming file
    base_name = os.path.basename(video_filename).replace(".mp4","")
    parts = base_name.split("_")
    device_id = parts[0]
    timestamp_str = parts[1]
    timestamp_iso = get_time_from_filename(video_filename)
    clip_id = parts[2]
    additional_note = parts[3]
    motion_group_id = parts[4]

    return device_id, timestamp_str, timestamp_iso, clip_id, additional_note, motion_group_id


def encode_and_upload(video_filename):
    incoming_filepath = os.path.join(INCOMING_DIR, video_filename)

    av1_video_filename = video_filename.replace(".mp4", ".mkv")
    output_path = os.path.join(ENCODED_DIR, av1_video_filename)
    logging.info(f"Encoding to: {output_path}")

    encode_success = encode_in_background_av1(incoming_filepath, output_path)
    
    upload_to_immich(av1_video_filename)


def upload_to_immich(video_filename):
    logging.info(f"Uploading {video_filename} to immich")

    encoded_video_path = os.path.join(ENCODED_DIR, video_filename)
    
    device_id, timestamp_str, timestamp_iso, clip_id, additional_note, motion_group_id = get_video_info(video_filename)

    device_asset_id = f"{clip_id}-{additional_note}-{motion_group_id}"
    try:
        with open(encoded_video_path, 'rb') as f:
            headers = {'x-api-key': IMMICH_API_KEY}
            files = {'assetData': f}
            data = {
                'deviceId': device_id,
                'deviceAssetId': device_asset_id,
                'fileCreatedAt': timestamp_iso,
                'fileModifiedAt': timestamp_iso
            }
            logging.info(f"Uploading video to Immich with deviceAssetId: {device_asset_id}")
            response = requests.post(IMMICH_UPLOAD_URL, files=files, data=data, headers=headers)

        logging.info(f"Upload response code: {response.status_code}")
        os.remove(encoded_video_path)
    except Exception as e:
        logging.error("Error during /upload", exc_info=True)


@app.route("/upload_clip", methods=["POST"])
def upload_clip():
    logging.info("Received POST /upload_clip request")
    if "file" not in request.files:
        logging.warning("No file uploaded")
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        logging.warning("Empty filename")
        return jsonify({"error": "Empty filename"}), 400

    video_filename = file.filename
    temp_path = os.path.join(INCOMING_DIR, video_filename)
    logging.debug(f"Saving the incoming video to {temp_path}")
    file.save(temp_path)
    logging.debug(f"Video saved.")
    
    threading.Thread(target=encode_and_upload, args=(video_filename,)).start()

    return jsonify({
        "status": "saved, ready to encode and upload",
        "saved_to": temp_path,
    }), 200


@app.route('/test', methods=['GET'])
def test_endpoint():
    logging.info("Received GET /test request")
    return "hello world"


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
