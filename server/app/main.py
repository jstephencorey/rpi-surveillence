"""
FastAPI server for distributed surveillance system.
Handles chunk uploads, storage, and API for video retrieval.
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field


# Configuration
DATA_DIR = Path(os.getenv("DATA_DIR", "/data/surveillence_data"))
INCOMING_DIR = DATA_DIR / "incoming"
PROCESSED_DIR = DATA_DIR / "processed"
MOTIONLESS_DIR = DATA_DIR / "motionless"
THUMBS_DIR = DATA_DIR / "thumbs"

# Ensure directories exist
def ensure_directories():
    """Create all required data directories."""
    for dir_path in [INCOMING_DIR, PROCESSED_DIR, MOTIONLESS_DIR, THUMBS_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"Ensured directory: {dir_path}")


# Pydantic models
class ChunkMetadata(BaseModel):
    """Metadata for a video chunk."""
    chunk_id: str = Field(..., description="Unique identifier for this chunk")
    device_id: str = Field(..., description="Device/camera identifier")
    camera_id: Optional[str] = Field(None, description="Specific camera on the device")
    start_time: str = Field(..., description="ISO 8601 timestamp when chunk recording started")
    duration: float = Field(..., description="Duration in seconds")
    codec: str = Field(..., description="Video codec (e.g., h264, mjpeg)")
    container: str = Field(..., description="Container format (e.g., mp4, h264, avi)")
    width: Optional[int] = Field(None, description="Video width in pixels")
    height: Optional[int] = Field(None, description="Video height in pixels")
    fps: Optional[float] = Field(None, description="Frames per second")
    
    # Server-populated fields (optional on upload)
    upload_time: Optional[str] = Field(None, description="ISO 8601 timestamp when uploaded")
    status: Optional[str] = Field("incoming", description="Current status: incoming, processed, motionless")
    has_motion: Optional[bool] = Field(None, description="Whether motion was detected")
    motion_score: Optional[float] = Field(None, description="Motion detection score")
    thumbnail_path: Optional[str] = Field(None, description="Path to generated thumbnail")


class UploadResponse(BaseModel):
    """Response from chunk upload."""
    success: bool
    chunk_id: str
    message: str
    saved_path: str


class ChunkExistsResponse(BaseModel):
    """Response from chunk exists check."""
    exists: bool
    chunk_id: str
    location: Optional[str] = None


# FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    ensure_directories()
    yield


app = FastAPI(
    title="Surveillance Server",
    description="Server for distributed camera surveillance system",
    version="1.0.0",
    lifespan=lifespan
)


def get_date_shard(timestamp_str: str) -> str:
    """Extract date shard (YYYY-MM-DD) from ISO timestamp."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        # Fallback to today if parsing fails
        return datetime.now().strftime("%Y-%m-%d")


def get_chunk_path(device_id: str, date_shard: str, chunk_id: str, container: str, base_dir: Path) -> Path:
    """Get the full path for a chunk."""
    chunk_dir = base_dir / device_id / date_shard
    chunk_dir.mkdir(parents=True, exist_ok=True)
    return chunk_dir / f"{device_id}_{chunk_id}.{container.lstrip('.')}"


def find_chunk(chunk_id: str, device_id: str, date_shard: str) -> Optional[Path]:
    """Find a chunk by ID across all storage directories."""
    for base_dir in [INCOMING_DIR, PROCESSED_DIR, MOTIONLESS_DIR]:
        chunk_path = base_dir / device_id / date_shard / f"{chunk_id}"
        # Try to find with any extension
        parent = chunk_path.parent
        if parent.exists():
            for file in parent.iterdir():
                if file.stem.endswith(chunk_id) or file.name.startswith(chunk_id):
                    return file
        # Also check with full filename pattern
        for ext in [".mp4", ".h264", ".mkv", ".avi", ".mjpeg"]:
            full_path = base_dir / device_id / date_shard / f"{device_id}_{chunk_id}{ext}"
            if full_path.exists():
                return full_path
    return None


def parse_chunk_filename(filename: str) -> tuple:
    """Parse chunk filename to extract device_id, timestamp, and chunk_id.
    
    Expected format: {device_id}_{YYYYMMDD}_{HHMMSS}_{chunk_id}.{ext}
    """
    name_without_ext = Path(filename).stem
    parts = name_without_ext.split("_")
    
    if len(parts) >= 4:
        device_id = parts[0]
        date_str = parts[1]
        time_str = parts[2]
        chunk_id = "_".join(parts[3:])  # Handle chunk_ids with underscores
        return device_id, date_str, time_str, chunk_id
    
    # Fallback: treat whole thing as chunk_id
    return "unknown", "", "", name_without_ext


@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "status": "ok",
        "service": "surveillance-server",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "directories": {
            "incoming": str(INCOMING_DIR),
            "processed": str(PROCESSED_DIR),
            "motionless": str(MOTIONLESS_DIR),
            "thumbs": str(THUMBS_DIR),
        }
    }


@app.post("/upload", response_model=UploadResponse)
async def upload_chunk(
    video: UploadFile = File(..., description="Video file chunk"),
    metadata: str = Form(..., description="JSON string of chunk metadata")
):
    """
    Upload a video chunk with its metadata.
    
    - **video**: The video file to upload
    - **metadata**: JSON string containing chunk metadata (device_id, start_time, etc.)
    
    No authentication required - endpoint is open to LAN.
    """
    try:
        # Parse metadata
        meta_dict = json.loads(metadata)
        chunk_meta = ChunkMetadata(**meta_dict)
        
        # Validate required fields
        if not chunk_meta.device_id or not chunk_meta.chunk_id:
            raise HTTPException(status_code=400, detail="device_id and chunk_id are required")
        
        # Get date shard from start_time
        date_shard = get_date_shard(chunk_meta.start_time)
        
        # Determine file extension
        container = chunk_meta.container.lower()
        if container in ["h264", "264"]:
            ext = ".h264"
        elif container == "mp4":
            ext = ".mp4"
        elif container in ["mkv", "matroska"]:
            ext = ".mkv"
        elif container in ["avi"]:
            ext = ".avi"
        elif container in ["mjpeg", "mjpg"]:
            ext = ".mjpeg"
        else:
            ext = f".{container}"
        
        # Build filename: {device_id}_{YYYYMMDD}_{HHMMSS}_{chunk_id}.{ext}
        dt = datetime.fromisoformat(chunk_meta.start_time.replace('Z', '+00:00'))
        date_str = dt.strftime("%Y%m%d")
        time_str = dt.strftime("%H%M%S")
        filename = f"{chunk_meta.device_id}_{date_str}_{time_str}_{chunk_meta.chunk_id}{ext}"
        
        # Get target directory and paths
        target_dir = INCOMING_DIR / chunk_meta.device_id / date_shard
        target_dir.mkdir(parents=True, exist_ok=True)
        
        video_path = target_dir / filename
        metadata_path = target_dir / f"{filename}.json"
        
        # Check if chunk already exists
        if video_path.exists():
            return UploadResponse(
                success=False,
                chunk_id=chunk_meta.chunk_id,
                message="Chunk already exists",
                saved_path=str(video_path)
            )
        
        # Save video file
        with open(video_path, "wb") as f:
            shutil.copyfileobj(video.file, f)
        
        # Update metadata with server info
        chunk_meta.upload_time = datetime.now().isoformat()
        chunk_meta.status = "incoming"
        
        # Save metadata sidecar
        with open(metadata_path, "w") as f:
            f.write(chunk_meta.model_dump_json(indent=2))
        
        return UploadResponse(
            success=True,
            chunk_id=chunk_meta.chunk_id,
            message="Chunk uploaded successfully",
            saved_path=str(video_path)
        )
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON metadata: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/chunk_exists", response_model=ChunkExistsResponse)
async def chunk_exists(
    chunk_id: str,
    device_id: str,
    date: Optional[str] = None
):
    """
    Check if a chunk already exists on the server.
    
    - **chunk_id**: The unique chunk identifier
    - **device_id**: The device/camera identifier
    - **date**: Optional date in YYYY-MM-DD format to narrow search
    
    Use this before uploading to avoid duplicates after crash/reboot.
    """
    if date:
        date_shard = date
    else:
        # Search across all dates for this device
        date_shard = ""
        for base_dir in [INCOMING_DIR, PROCESSED_DIR, MOTIONLESS_DIR]:
            device_dir = base_dir / device_id
            if device_dir.exists():
                for date_dir in device_dir.iterdir():
                    if date_dir.is_dir():
                        location = find_chunk(chunk_id, device_id, date_dir.name)
                        if location:
                            return ChunkExistsResponse(
                                exists=True,
                                chunk_id=chunk_id,
                                location=str(location)
                            )
    
    location = find_chunk(chunk_id, device_id, date_shard) if date_shard else None
    
    return ChunkExistsResponse(
        exists=location is not None,
        chunk_id=chunk_id,
        location=str(location) if location else None
    )


@app.get("/api/cameras")
async def list_cameras():
    """List all cameras that have uploaded chunks."""
    cameras = []
    
    # Scan incoming directory for device IDs
    for base_dir in [INCOMING_DIR, PROCESSED_DIR, MOTIONLESS_DIR]:
        if base_dir.exists():
            for device_dir in base_dir.iterdir():
                if device_dir.is_dir():
                    device_id = device_dir.name
                    if device_id not in [c["id"] for c in cameras]:
                        # Count total chunks for this device
                        chunk_count = 0
                        for date_dir in device_dir.iterdir():
                            if date_dir.is_dir():
                                chunk_count += len(list(date_dir.glob("*.*")))
                        
                        cameras.append({
                            "id": device_id,
                            "name": device_id,  # Will be enhanced later with config
                            "chunk_count": chunk_count,
                            "has_incoming": (INCOMING_DIR / device_id).exists(),
                            "has_processed": (PROCESSED_DIR / device_id).exists(),
                        })
    
    return {"cameras": cameras}


@app.get("/api/cameras/{camera_id}/chunks")
async def list_chunks(
    camera_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    motion_only: bool = False,
    status: Optional[str] = None  # "incoming", "processed", "motionless", or "all"
):
    """List chunks for a specific camera with optional filtering."""
    chunks = []
    
    # Determine which directories to scan
    if status == "incoming":
        dirs_to_scan = [INCOMING_DIR]
    elif status == "processed":
        dirs_to_scan = [PROCESSED_DIR]
    elif status == "motionless":
        dirs_to_scan = [MOTIONLESS_DIR]
    else:
        dirs_to_scan = [INCOMING_DIR, PROCESSED_DIR, MOTIONLESS_DIR]
    
    for base_dir in dirs_to_scan:
        camera_dir = base_dir / camera_id
        if not camera_dir.exists():
            continue
        
        for date_dir in camera_dir.iterdir():
            if not date_dir.is_dir():
                continue
            
            for file_path in date_dir.iterdir():
                if file_path.suffix == ".json":
                    continue  # Skip metadata files
                
                # Try to load metadata
                meta_path = date_dir / f"{file_path.name}.json"
                meta_data = {}
                if meta_path.exists():
                    try:
                        with open(meta_path) as f:
                            meta_data = json.load(f)
                    except:
                        pass
                
                # Apply motion filter
                if motion_only and not meta_data.get("has_motion", False):
                    continue
                
                # Apply date filters
                chunk_start = meta_data.get("start_time", "")
                if start and chunk_start < start:
                    continue
                if end and chunk_start > end:
                    continue
                
                chunks.append({
                    "filename": file_path.name,
                    "path": str(file_path),
                    "device_id": meta_data.get("device_id", camera_id),
                    "chunk_id": meta_data.get("chunk_id", file_path.stem),
                    "start_time": meta_data.get("start_time", ""),
                    "duration": meta_data.get("duration", 0),
                    "codec": meta_data.get("codec", "unknown"),
                    "status": meta_data.get("status", "unknown"),
                    "has_motion": meta_data.get("has_motion"),
                    "motion_score": meta_data.get("motion_score"),
                })
    
    # Sort by start time
    chunks.sort(key=lambda x: x["start_time"])
    
    return {
        "camera_id": camera_id,
        "count": len(chunks),
        "chunks": chunks
    }


@app.get("/video/{camera_id}/{filename}")
async def get_video(camera_id: str, filename: str):
    """Stream a video chunk. Supports HTTP range requests for scrubbing."""
    # Search in all directories
    for base_dir in [INCOMING_DIR, PROCESSED_DIR, MOTIONLESS_DIR]:
        # Search through date shards
        camera_dir = base_dir / camera_id
        if camera_dir.exists():
            for date_dir in camera_dir.iterdir():
                if date_dir.is_dir():
                    video_path = date_dir / filename
                    if video_path.exists():
                        return FileResponse(
                            video_path,
                            media_type="video/mp4",
                            headers={
                                "Accept-Ranges": "bytes",
                            }
                        )
    
    raise HTTPException(status_code=404, detail="Video not found")


@app.get("/thumb/{camera_id}/{filename}")
async def get_thumbnail(camera_id: str, filename: str):
    """Get a thumbnail for a chunk."""
    # Thumbnails have .jpg extension
    thumb_filename = Path(filename).stem + ".jpg"
    
    for base_dir in [THUMBS_DIR]:
        camera_dir = base_dir / camera_id
        if camera_dir.exists():
            for date_dir in camera_dir.iterdir():
                if date_dir.is_dir():
                    thumb_path = date_dir / thumb_filename
                    if thumb_path.exists():
                        return FileResponse(thumb_path, media_type="image/jpeg")
    
    raise HTTPException(status_code=404, detail="Thumbnail not found")
