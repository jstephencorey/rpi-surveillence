from flask import Flask, request, jsonify
import os, tempfile, subprocess, shutil, logging
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


OUTPUT_DIR = "/data/video"
INCOMING_DIR = os.path.join(OUTPUT_DIR, "incoming")
LOW_QUALITY = "44" #Found through testing to be a as low as I could reasonably go without loosing too much quality


os.makedirs(INCOMING_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


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


def encode_in_background(input_path, output_path):
    """Run ffmpeg H.265 NVENC encode asynchronously."""
    logging.info("Running background encode now")
    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-hwaccel", "cuda",
            "-i", input_path,
            "-c:v", "hevc_nvenc",
            "-preset", "p7",       # very slow, highest quality
            "-cq", "28",           # constant quality (lower = higher quality)
            "-c:a", "copy",         # copy audio
            output_path
        ], check=True)
        os.remove(input_path)
        logging.info(f"Finished [ENCODED] {output_path}")
    except subprocess.CalledProcessError as e:
        logging.warning(f"[ERROR] FFmpeg failed for {input_path}: {e}")

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
            "-global_quality", "30", # found through some experimentation
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

    temp_path = os.path.join(INCOMING_DIR, file.filename)
    file.save(temp_path)

    device_id, timestamp_str, timestamp_iso, clip_id, additional_note, motion_group_id = get_video_info(file.filename)

    output_file_name = f"{device_id}_{timestamp_str}_{clip_id}_{additional_note}_{motion_group_id}.mp4"

    output_path = os.path.join(OUTPUT_DIR, output_file_name)
    logging.info(f"Saving to Output {output_path}")
    # This is an option that doesn't encode it at all, and will let my home computer do all of that
    # os.rename(temp_path, output_path)
    # Spawn encoding in background to encode with h265
    threading.Thread(target=encode_in_background_av1, args=(temp_path, output_path)).start()

    return jsonify({
        "status": "uploaded",
        "saved_to": temp_path,
        "encoding_to": output_path
    }), 200



# Load secrets from .env
SECRET_KEY = os.getenv("SECRET_KEY")
IMMICH_API_KEY = os.getenv("IMMICH_API_KEY")
IMMICH_UPLOAD_URL = str(os.getenv("IMMICH_UPLOAD_URL"))

def get_iso8601_zoned_timestamp():
    tz = pytz.timezone(os.getenv("TIMEZONE", "America/Denver"))  # fallback to Mountain Time
    now = datetime.now(tz)
    return now.isoformat()

@app.route('/test', methods=['GET'])
def test_endpoint():
    logging.info("Received GET /test request")
    return "hello world"

@app.route('/upload', methods=['POST'])
def receive_images():
    logging.info("Received POST /upload request")
    temp_dir = tempfile.mkdtemp()
    filenames = []

    try:
        # Expect deviceId in form data
        logging.info("beginning to process the request")
        device_id = request.form.get("deviceId")
        if not device_id:
            logging.warning("Missing deviceId in form data")
            return {"status": "error", "message": "Missing deviceId"}, 400

        logging.info(f"Device ID: {device_id}")

        images = request.files.getlist("images")
        logging.info(f"Number of images received: {len(images)}")

        for i, file in enumerate(images):
            path = os.path.join(temp_dir, f"frame_{i:03}.jpg")
            file.save(path)
            filenames.append(path)
            logging.debug(f"Saved frame: {path}")

        video_path = os.path.join(temp_dir, "output.mp4")
        logging.info(f"Generating video at: {video_path}")

        result = subprocess.run([
            "ffmpeg", "-y",
            "-framerate", "10",
            "-i", os.path.join(temp_dir, "frame_%03d.jpg"),
            "-c:v", "libx265",
            "-pix_fmt", "yuv420p",
            video_path
        ], check=True, capture_output=True, text=True)

        if result.returncode != 0:
            logging.error(f"ffmpeg failed: {result.stderr}")

        logging.info("Video generation complete")

        # Upload video to Immich
        with open(video_path, 'rb') as f:
            headers = {'x-api-key': IMMICH_API_KEY}
            files = {'assetData': f}
            timestamp = get_iso8601_zoned_timestamp()
            device_asset_id = f"{device_id}_{str(uuid.uuid4())}"
            data = {
                'deviceId': device_id,
                'deviceAssetId': device_asset_id,
                'fileCreatedAt': timestamp,
                'fileModifiedAt': timestamp
            }
            logging.info(f"Uploading video to Immich with deviceAssetId: {device_asset_id}")
            response = requests.post(IMMICH_UPLOAD_URL, files=files, data=data, headers=headers)

        logging.info(f"Upload response code: {response.status_code}")
        return {"status": "success", "immich_response": response.json()}, response.status_code

    except Exception as e:
        logging.error("Error during /upload", exc_info=True)
        return {"status": "error", "message": str(e)}, 500

    finally:
        logging.info("Reached the finally chunk of processing the images/video")
        shutil.rmtree(temp_dir)
        logging.info(f"Cleaned up temp directory: {temp_dir}")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
