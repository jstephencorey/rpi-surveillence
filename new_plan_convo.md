# Distributed Offline Security Camera Architecture
Created: 6/6/2026, 7:15:39 PM
Last Updated: 6/6/2026, 9:43:10 PM
---

### User

I have a project where I want to turn a bunch of raspberry pi cameras and esp32 cameras into security cameras/trail cameras. But a part of the eventual requirements is that The cameras be able to be offline for a while, then upload the camera footage later. 

I had initially been planning on doing on device motion detection for cameras attached to a raspberry pi zero 2 w, But it's really hard on such a compute constrained device to do motion detection in real time. Possible but difficult. It becomes basically impossible on an esp32 cam, iirc. 

I have a server with an Intel a770 and an 3060, so it's got much more video processing chops than any edge device. 

I would only use the rpis for offline recording, but I was realizing that esp32cam devices might be nice for cheap low quality cameras.

I guess I have two main architectural questions, "on device motion detection or off device motion detection" and "use frigate or write my own thing". 

There are benefits for on device motion detection, especially if I'm running the pi off of a battery or running it offline, to save on Wi-Fi and storage respectively. But it also makes things a lot more complicated to build. And it might really be nice to just do it where the pi or esp32 always sends its data back and my computer can handle all the motion detection. 

Frigate is nice in that it has a lot of what I want/would build already built in - camera handling, a way to view live streams, motion detection, and "save this forever vs. ditch it after a little bit of time". But it also currently doesn't really have a way to stream back in data that I took at a different time/load it in bulk, and it doesn't have any sort of auth. Also, esp32 cameras require a little bit more configuration with frigate because of the MJpeg stuff not being something frigate natively supports. 

I also have a different project involving a robotic Chicken Coop that I eventually want to build that will likely be similar in various ways, using a mini PC with external esp32 cams and other things to control motors and take pictures etc. The sort of code that I write myself for something like this might be nice, But I also might just use home assistant (I'm not really familiar with that software or how it works). 

Idk, thoughts on all that?


---

### Assistant (claude-4.5-sonnet)

This is a fun problem with some interesting tradeoffs! Let me think through the architecture with you.

## Motion Detection: On-Device vs Server-Side

For your use case (offline operation + delayed upload), I'd lean toward **server-side motion detection**. Here's why:

**Edge devices just record continuously:**
- RPi Zero 2 W: Record H.264 to local storage (SD card or USB drive)
- ESP32-CAM: Record MJPEG to SD card (they support this natively)
- Simple, reliable, works offline
- Low compute overhead = better battery life

**Server handles the intelligence:**
- When devices come back online, bulk upload footage
- Server does motion detection on uploaded footage (A770 handles this easily)
- Extract/save motion events, discard quiet periods
- Your A770 can process video way faster than real-time

This gives you offline operation benefits without the complexity of edge ML. The only downside is you need enough storage on the edge devices, but SD cards are cheap.

## Frigate vs Custom

I'd say **start custom, but steal ideas from Frigate**. Here's my reasoning:

**Frigate's gaps for your use case:**
- No bulk upload/delayed processing (it's designed for live streams)
- No auth (fine for isolated networks, not great for your setup)
- ESP32-CAM support is clunky

**Custom approach could be:**
```python
# Edge device: simple upload client
# - Monitor local video directory
# - Upload completed videos when online
# - Delete after confirmed upload

# Server: processing pipeline
# - Receive uploaded videos
# - Motion detection (OpenCV or similar)
# - Extract events, generate thumbnails
# - Web UI for viewing (FastAPI + HTMX?)
```

You could use existing tools for pieces:
- Motion detection: OpenCV, or Motion library
- Video processing: ffmpeg
- Storage: Just filesystem + SQLite for metadata
- Auth: Basic HTTP auth or OAuth

## ESP32-CAM Considerations

They're great for cheap cameras, but keep in mind:
- MJPEG is storage-hungry (vs H.264 on RPi)
- Resolution/quality limitations
- More finicky hardware

Maybe use ESP32-CAMs for low-priority areas (garage, shed) and RPis for important spots?

## Architecture Sketch

```
Edge Devices (RPi/ESP32)
  ↓ (record locally)
  └─ [local storage]
      ↓ (when online)
      └─ HTTP upload to server

Server
  ↓ (receive uploads)
  ├─ [incoming queue]
  ├─ [motion detection worker]
  ├─ [event extraction]
  └─ [web UI + storage]
```

## For the Chicken Coop Project

That sounds like a different beast - real-time control loops, sensors, etc. I'd probably:
- Use Home Assistant for the coop (it's good at IoT orchestration)
- Keep your camera system separate (they solve different problems)
- Maybe have them talk to each other via MQTT or webhook if needed

Want me to sketch out what a minimal MVP of the custom camera system might look like? Or dive deeper into any particular part?


---

### User

If I do 10 second chunks, how do I recombine them later? Or do I even?


---

### Assistant (claude-4.5-sonnet)

Great question! You have a few options:

## Option 1: Don't Recombine (Recommended)

Just keep them as 10-second chunks and treat each as a separate "segment":

```python
# Metadata structure
{
  "camera_id": "front_porch",
  "timestamp": "2026-06-07T15:30:00Z",
  "filename": "front_porch_20260607_153000.mp4",
  "duration": 10,
  "has_motion": true,
  "motion_score": 0.75
}
```

**Playback:** Your web UI stitches them together on-the-fly:
- Load sequential segments
- Use HTML5 video with playlist or Media Source Extensions
- Seamless playback across chunks

**Benefits:**
- Simple upload/processing pipeline
- Easy to delete boring chunks
- Can extract just the interesting parts
- Parallel processing of chunks

## Option 2: Recombine with ffmpeg (If Needed)

If you need a single file for motion events:

```bash
# Create concat file
echo "file 'chunk_001.mp4'" > list.txt
echo "file 'chunk_002.mp4'" >> list.txt
echo "file 'chunk_003.mp4'" >> list.txt

# Recombine (no re-encoding, super fast)
ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4
```

This is instantaneous since it just concatenates without re-encoding.

**When to do this:**
- Only for motion events you want to keep long-term
- After motion detection identifies interesting periods
- Example: Chunks 42-47 had motion → combine into one "event video"

## Option 3: Continuous Recording + Segmentation

Record continuously but segment for storage:

```python
# On RPi, record in segments
ffmpeg -i /dev/video0 -c:v h264_v4l2m2m \
  -segment_time 10 -f segment \
  -reset_timestamps 1 \
  output_%03d.mp4
```

Server receives individual segments, processes each, then:
- Keep motion segments separate
- Delete quiet segments
- Optionally combine motion segments into events

## My Recommendation

**Keep as 10-second chunks** and build your UI to handle them. It's cleaner architecturally:

```python
# Playback API endpoint
@app.get("/camera/{camera_id}/playback")
def get_playback(camera_id: str, start: datetime, end: datetime):
    chunks = db.get_chunks(camera_id, start, end)
    return {
        "playlist": [
            {"url": f"/video/{c.filename}", "start": c.timestamp}
            for c in chunks
        ]
    }
```

Front-end plays them sequentially. If you later want combined videos for specific events, generate them on-demand or as a background job.

Does that make sense? The key insight is that keeping things chunked gives you more flexibility.


---

### User

Yeah. Makes sense 😁


---

### Assistant (claude-4.5-sonnet)

Awesome! 😊

So your pipeline is pretty straightforward then:
- Edge devices: chunk, store, upload when online
- Server: motion detect each chunk, keep/toss based on results
- UI: play chunks like a playlist

The A770 will chew through motion detection way faster than real-time, so even bulk uploads should process quickly.

Let me know if you want to brainstorm the edge device upload logic or server processing pipeline! The sync/resume logic for interrupted uploads could be fun to think through.


---

### User

Talk me through the full process, including how to encode timestamps in the videos and when to reencode, etc.


---

### Assistant (claude-4.5-sonnet)

# Full Pipeline Walkthrough

## Edge Device: Recording & Upload

### Recording with Timestamps

**RPi Zero 2 W:**
```bash
# Record 10-second segments with timestamp in filename
# Use hardware encoder for efficiency
ffmpeg -f v4l2 -i /dev/video0 \
  -c:v h264_v4l2m2m \
  -b:v 1M \
  -segment_time 10 \
  -f segment \
  -strftime 1 \
  -reset_timestamps 1 \
  /storage/camera1_%Y%m%d_%H%M%S.mp4
```

The `-strftime 1` flag lets you use time formatting in filenames, so you get:
- `camera1_20260607_150000.mp4`
- `camera1_20260607_150010.mp4`
- etc.

**Timestamp encoding:**
- Filename IS the timestamp (parse it later)
- Don't burn timestamps into video (no re-encoding needed)
- Optionally store metadata in a sidecar `.json` file:

```python
# On RPi after each chunk completes
{
  "filename": "camera1_20260607_150000.mp4",
  "camera_id": "front_porch",
  "start_time": "2026-06-07T15:00:00Z",
  "duration": 10.0,
  "uploaded": false
}
```

**ESP32-CAM:**
Similar concept but MJPEG:
```cpp
// Record to SD card in chunks
// Filename: camera2_20260607_150000.mjpeg
// Store metadata in separate file
```

### Upload Logic

```python
# upload_daemon.py running on edge device
import os
import requests
from pathlib import Path
import json

UPLOAD_URL = "https://yourserver.com/api/upload"
STORAGE_DIR = "/storage"

def upload_chunk(video_path, metadata_path):
    with open(video_path, 'rb') as v, open(metadata_path, 'r') as m:
        files = {
            'video': v,
            'metadata': m.read()
        }
        response = requests.post(
            UPLOAD_URL, 
            files=files,
            timeout=300  # 5 min timeout for slow connections
        )
        return response.status_code == 200

def main():
    while True:
        # Find chunks not yet uploaded
        for video in sorted(Path(STORAGE_DIR).glob("*.mp4")):
            meta = video.with_suffix('.json')
            
            # Skip if already uploaded
            if not meta.exists():
                continue
                
            metadata = json.loads(meta.read_text())
            if metadata.get('uploaded'):
                continue
            
            # Try upload
            if upload_chunk(video, meta):
                # Mark as uploaded
                metadata['uploaded'] = True
                metadata['upload_time'] = datetime.utcnow().isoformat()
                meta.write_text(json.dumps(metadata))
                
                # Delete video and metadata after 24h
                # (keep metadata for reconciliation)
                os.remove(video)
                
        time.sleep(60)  # Check every minute
```

**Resume logic:**
- If upload fails mid-transfer, retry from beginning (10-sec chunks = acceptable)
- For larger chunks, could use resumable uploads (more complex)
- Track upload state in metadata JSON

## Server: Receiving & Processing

### Upload Endpoint

```python
# server/api.py
from fastapi import FastAPI, UploadFile, File, Form
from pathlib import Path
import json
import shutil

app = FastAPI()

INCOMING_DIR = Path("/data/incoming")
PROCESSED_DIR = Path("/data/processed")
ARCHIVE_DIR = Path("/data/archive")

@app.post("/api/upload")
async def upload_chunk(
    video: UploadFile = File(...),
    metadata: str = Form(...)
):
    meta = json.loads(metadata)
    camera_id = meta['camera_id']
    filename = meta['filename']
    
    # Save to incoming directory
    incoming_path = INCOMING_DIR / camera_id / filename
    incoming_path.parent.mkdir(parents=True, exist_ok=True)
    
    with incoming_path.open('wb') as f:
        shutil.copyfileobj(video.file, f)
    
    # Save metadata
    meta_path = incoming_path.with_suffix('.json')
    meta_path.write_text(json.dumps(meta))
    
    # Queue for processing
    queue_for_motion_detection(incoming_path)
    
    return {"status": "success"}
```

### Motion Detection Worker

```python
# server/motion_detector.py
import cv2
import numpy as np
from pathlib import Path

def detect_motion(video_path: Path):
    """
    Returns motion score (0-1) and frames with motion
    No re-encoding happens here!
    """
    cap = cv2.VideoCapture(str(video_path))
    
    prev_frame = None
    motion_frames = []
    total_frames = 0
    motion_score = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        total_frames += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        if prev_frame is None:
            prev_frame = gray
            continue
        
        # Frame difference
        frame_delta = cv2.absdiff(prev_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        
        # Count changed pixels
        changed_pixels = np.sum(thresh) / 255
        total_pixels = thresh.shape[0] * thresh.shape[1]
        change_ratio = changed_pixels / total_pixels
        
        if change_ratio > 0.01:  # 1% of pixels changed
            motion_frames.append(total_frames)
            motion_score += change_ratio
        
        prev_frame = gray
    
    cap.release()
    
    return {
        'has_motion': len(motion_frames) > 0,
        'motion_score': motion_score / total_frames if total_frames > 0 else 0,
        'motion_frames': motion_frames,
        'total_frames': total_frames
    }

def process_chunk(video_path: Path):
    """Process incoming chunk"""
    meta_path = video_path.with_suffix('.json')
    metadata = json.loads(meta_path.read_text())
    
    # Run motion detection
    motion_result = detect_motion(video_path)
    metadata['motion'] = motion_result
    
    # Decide what to do
    if motion_result['has_motion']:
        # Keep it - move to processed
        dest = PROCESSED_DIR / metadata['camera_id'] / video_path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(video_path, dest)
        
        # Generate thumbnail (optional)
        generate_thumbnail(dest)
        
        # Update metadata
        meta_dest = dest.with_suffix('.json')
        meta_dest.write_text(json.dumps(metadata))
        
    else:
        # No motion - move to archive (delete after N days)
        archive = ARCHIVE_DIR / metadata['camera_id'] / video_path.name
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(video_path, archive)
        
        # Still save metadata for gaps
        meta_archive = archive.with_suffix('.json')
        meta_archive.write_text(json.dumps(metadata))
    
    # Cleanup incoming metadata
    meta_path.unlink(missing_ok=True)
```

## When to Re-encode (Rarely!)

**Don't re-encode if:**
- Just moving files around ✅
- Serving for playback ✅
- Combining chunks with `ffmpeg -c copy` ✅

**Only re-encode if:**
- Converting ESP32 MJPEG to H.264 for long-term storage
- Creating thumbnails/preview clips
- Burning in timestamps for export (user requests it)

### Re-encoding Examples

**Convert MJPEG to H.264:**
```bash
# For long-term storage of ESP32 footage
ffmpeg -i camera2_20260607_150000.mjpeg \
  -c:v libx264 -preset fast -crf 23 \
  -c:a copy \
  camera2_20260607_150000.mp4
```

**Generate thumbnail:**
```python
def generate_thumbnail(video_path: Path):
    """Extract middle frame as thumbnail"""
    thumb_path = video_path.with_suffix('.jpg')
    
    # Get middle frame, no re-encoding of video
    subprocess.run([
        'ffmpeg', '-i', str(video_path),
        '-ss', '00:00:05',  # 5 seconds in
        '-vframes', '1',
        '-q:v', '2',
        str(thumb_path)
    ])
```

**Burn timestamp for user export:**
```bash
# Only when user explicitly wants it
ffmpeg -i input.mp4 \
  -vf "drawtext=text='%{pts\:gmtime\:1717732800\:%Y-%m-%d %H\\\:%M\\\:%S}':x=10:y=10:fontsize=24:fontcolor=white" \
  -c:v libx264 -preset fast -crf 23 \
  output_with_timestamp.mp4
```

## Storage Management

```python
# server/cleanup.py
from datetime import datetime, timedelta

def cleanup_old_footage():
    """Run daily"""
    
    # Delete archive (no motion) after 7 days
    cutoff = datetime.utcnow() - timedelta(days=7)
    for video in ARCHIVE_DIR.rglob("*.mp4"):
        meta = json.loads(video.with_suffix('.json').read_text())
        if datetime.fromisoformat(meta['start_time']) < cutoff:
            video.unlink()
            video.with_suffix('.json').unlink()
    
    # Keep processed (motion) for 30 days
    cutoff = datetime.utcnow() - timedelta(days=30)
    for video in PROCESSED_DIR.rglob("*.mp4"):
        meta = json.loads(video.with_suffix('.json').read_text())
        if datetime.fromisoformat(meta['start_time']) < cutoff:
            # Could move to cold storage instead
            video.unlink()
            video.with_suffix('.json').unlink()
```

## Playback UI

```python
# server/playback.py
@app.get("/api/playback/{camera_id}")
def get_playback(
    camera_id: str,
    start: str,
    end: str,
    motion_only: bool = True
):
    """Return playlist of chunks"""
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    
    search_dir = PROCESSED_DIR if motion_only else ARCHIVE_DIR
    chunks = []
    
    for video in (search_dir / camera_id).glob("*.mp4"):
        meta = json.loads(video.with_suffix('.json').read_text())
        chunk_time = datetime.fromisoformat(meta['start_time'])
        
        if start_dt <= chunk_time <= end_dt:
            chunks.append({
                'url': f'/video/{camera_id}/{video.name}',
                'start': meta['start_time'],
                'duration': meta['duration'],
                'has_motion': meta.get('motion', {}).get('has_motion', False),
                'thumbnail': f'/thumb/{camera_id}/{video.stem}.jpg'
            })
    
    return {'chunks': sorted(chunks, key=lambda x: x['start'])}
```

## Summary: When Does Re-encoding Happen?

1. **Never** for H.264 chunks from RPi (already efficient)
2. **Optional** for ESP32 MJPEG → H.264 conversion (save space)
3. **Only for derivatives**: thumbnails, exports with burned-in timestamps
4. **Core pipeline is zero-copy**: upload → detect → move/delete

The key is: **filename = timestamp**, no need to burn it into video unless specifically requested!

Make sense?


---
