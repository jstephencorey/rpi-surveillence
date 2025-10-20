from flask import Flask, request
import os, tempfile, subprocess, shutil, logging
import requests
from dotenv import load_dotenv
from datetime import datetime
import pytz
import uuid

# Load environment variables
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # increase if needed


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

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