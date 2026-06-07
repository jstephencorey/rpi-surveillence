# Plan: Move to a Server-Centric Distributed Camera Architecture

This plan describes how to evolve the current repo from "on-device motion detection + Immich upload" to a "dumb edge / smart server" architecture that also supports offline operation and ESP32-CAM devices.

## 1. Guiding Architectural Shift

- Edge devices (Raspberry Pi Zero 2 W, ESP32-CAM) become **simple recorders**: capture short fixed-length chunks to local storage, then upload whenever a network is available.
- The **server** (with the A770/3060) becomes the smart side: receives chunks, runs motion detection, sorts/retains/discards, generates thumbnails, and exposes a playback UI.
- **No recombination** of chunks. They stay as ~10s segments; the UI stitches them on the fly via a playlist.
- **Filename = timestamp** (plus device id + chunk id). Timestamps are not burned into the video. Re-encoding is avoided except for narrow cases (MJPEG→H.264, thumbnails; future: optional AV1 archival).
- The project becomes **offline-first**: edge devices keep recording and queueing while disconnected, then drain their queue to the server when reconnected.
- **Uploads are not authenticated.** Devices just push chunks to the server when they can reach it; the web UI is the only thing gated by auth (user login).

## 2. Edge Device Plan – Raspberry Pi

Goal: strip the Pi down to "record + queue + upload + manage local disk".

### 2.1 Capture changes (`capture_lib.py`, `capture_local.py`, `capture_upload.py`)
- Reduce segment length from 20s to **10s** to match server-side chunk model. (configurable on the device, server should be agnostic to clip length within reason)
- Switch filename pattern to **timestamp-based** using `rpicam-vid --strftime` (e.g. `{device_id}_{YYYYMMDD}_{HHMMSS}.h264` or `.mp4`).
- Keep H.264, hardware encoder, and the I-frame cadence (still useful for fast server-side decode).
- After each segment is finalized, write a **sidecar JSON metadata file** describing it: device id, camera id, start time, duration, codec, container, upload state, and a stable chunk id. This becomes the source of truth for the upload daemon and the server.
- Drop on-device assumptions about motion (no need to favor h264 keyframe sampling on the edge).

### 2.2 Remove on-device motion detection
- Delete `motion_postprocess_lib.py`, `motion_postprocess_local.py`, `motion_postprocess_upload.py`, and their service files.
- Remove `motion_postprocess_*.service` references from `setup_local.sh`, `setup_upload.sh`, and `shutdown_services.sh`.
- Remove the `motion_calibration.ipynb` / `motion_detection.ipynb` notebooks from the edge workflow (move to a `server/notebooks/` area, or archive, depending on whether you still want them for tuning the server detector).

### 2.3 Upload daemon (`clip_uploader.py`) overhaul
- Watch the buffer/chunk directory instead of a "clips" directory.
- For each finalized chunk:
  - Confirm stability (already done).
  - POST the chunk **plus its metadata JSON** as a single request. **No auth header / API key** – the upload endpoint is open.
  - On success, mark `uploaded: true` in the metadata file rather than deleting immediately.
  - Delete the video after a configurable **grace period** (see §2.4) so a brief server problem doesn't lose data. The metadata JSON may be kept longer than the video if the user wants a local audit trail of what was sent.
- Add basic retry/backoff and a server-side "do you already have this chunk id?" pre-check to avoid duplicate uploads after reboot/crash.
- Add **disk-pressure handling**: when local storage gets tight, drop oldest *uploaded* chunks first, then oldest *unuploaded* chunks (configurable), and log loudly.

### 2.4 Device configuration file (new)
Each edge device reads a single config file (e.g. `device.yaml`) that controls its behavior. This keeps device-specific settings out of code and out of the systemd unit files. Minimum fields:

- `device_name` (string, required) – friendly name for the device, used in the web UI and as the device id embedded in the filename pattern.
- `server_url` (string, required) – base URL of the upload server.
- `upload_enabled` (bool, optional, default `true`) – set to `false` to skip uploads entirely. Useful when you know the device is on a network with no route to the server, or when you want to run a capture-only deployment. With this off, the uploader is a no-op and chunks are only removed when local disk-pressure rules fire.
- `upload_grace_period_seconds` (int, default e.g. `3600`) – how long to keep a successfully uploaded video locally before deleting it. `0` is valid and means "delete immediately after the server acknowledges the upload". The metadata JSON sidecar is kept longer if you want a local audit trail.
- `disk_pressure_*` (optional) – thresholds for the disk-pressure handling described in §2.3.
- `clip_length` Defaults to 10 seconds, good reasonable default for now, how long each clip should be before being uploaded to the server.
- **Other settings may be added later** (per-camera retention, detector hints, etc.) without touching code paths.

The capture script, the uploader, and any cleanup job all read from this file so behavior is consistent across services.

### 2.5 Local-only mode
There is no separate "local-only mode" in the design. A device is in local-only operation simply when the uploader service is not running. Operationally this is one of:

- Set `upload_enabled: false` in `device.yaml` (the uploader daemon self-disables and exits cleanly on its next tick, so you don't even need to stop the service).
- Or just don't enable the `clip_uploader` service in the first place (the local setup script doesn't install it).

Either way, the capture pipeline runs unchanged: chunks are written to the buffer directory with sidecar metadata, the same as the upload case. When the device is brought back to a network that can reach the server, the user re-enables uploads (flip `upload_enabled` to `true`, or start the service) and the uploader catches up on the queued chunks. There is nothing else to "switch over" — the chunk format and metadata schema are identical, so a local-only device's storage can be ingested by the server later with no conversion step.

`capture_local` and `capture_upload` therefore differ only in the target buffer directory and the systemd units the setup script installs. No on-device motion detection in either path.

## 3. Edge Device Plan – ESP32-CAM (new)

Add first-class support as a separate, parallel edge platform.

- New top-level directory (e.g. `esp32cam/`) containing an Arduino/PlatformIO sketch.
- Sketch responsibilities:
  - Record MJPEG to SD card in ~10s chunks using the same `{device_id}_{timestamp}_{chunk_id}` filename convention.
  - Write a small sidecar metadata file describing each chunk.
  - When Wi-Fi is available, upload chunks to the same server endpoint as the Pi. **No auth required.**
  - Use the same "mark uploaded, delete after grace period" pattern adapted to FAT/SD constraints.
  - Read a small on-device config (similar to §2.4) for `device_name`, `server_url`, `upload_enabled`, and `upload_grace_period_seconds`.
- Document expected limitations (lower resolution, MJPEG storage cost, finicky hardware) and recommend ESP32-CAMs only for low-priority spots.
- Provide a `esp32cam/README.md` with flashing/wiring/config steps mirroring the Pi README structure.

## 4. Server Plan

The app needs to evolve from "encode + push to Immich" to a full camera backend. **Migrate the existing Flask app to FastAPI** – the async ergonomics, type-driven OpenAPI docs, and background-worker story are worth the one-time migration cost.

### 4.1 Directory + storage layout
Standardize on something like:
- `data/incoming/<camera_id>/YYYY-MM-DD/` – freshly uploaded chunks awaiting processing. Date-sharded so scans are bounded and `/chunk_exists` is O(1).
- `data/processed/<camera_id>/YYYY-MM-DD/` – chunks where motion was detected; long retention.
- `data/motionless/<camera_id>/YYYY-MM-DD/` – chunks with no motion; shorter retention (e.g., 7 days). (Was previously `data/archive/`; the new name describes the contents more clearly.)
- `data/thumbs/<camera_id>/YYYY-MM-DD/` – generated thumbnails per chunk.

Each chunk carries its sidecar JSON metadata as it moves between directories. Filenames embed `{device_id}_{YYYYMMDD}_{HHMMSS}_{chunk_id}` so the date can be parsed from the name without opening the file.

> Exports, derived clips, and re-encoded archives are intentionally **out of scope for now**. A `data/exports/` directory will be added back in a later phase.

### 4.2 Upload endpoint (`server/app.py` – FastAPI)
- The endpoint accepts:
  - The video file.
  - The sidecar metadata JSON.
  - **No auth header / API key.** Uploads are open; the assumption is the server is reachable only on a trusted LAN. This is what lets the Pi/ESP32 just upload.
- Save into `data/incoming/<camera_id>/` and enqueue for processing.
- Add a companion endpoint like `/chunk_exists?id=...` so edge devices can pre-check before uploading after a crash.

### 4.3 Motion detection worker (new)
- Background worker (asyncio task, thread, or external worker process) consumes incoming chunks.
- Reuse the OpenCV-based logic from the existing `motion_postprocess_lib.py` (frame diff, ratio threshold) but adapt it to operate on a **single chunk at a time** instead of streaming segments.
- Output per-chunk `motion` block in metadata: `has_motion`, `motion_score`, optional list of motion frame indices, detector config used.
- On finish:
  - Move motion-positive chunks + metadata to `data/processed/<camera_id>/`.
  - Move motion-negative chunks + metadata to `data/motionless/<camera_id>/`.
  - Generate a thumbnail (middle frame or a frame from a motion region) to `data/thumbs/`.
- Make detector parameters (pixel threshold, change ratio, blur kernel, motion frame ratio) configurable per camera via a single server config file (e.g. `cameras.yaml` / `cameras.toml`). One block per camera; the motion worker reads its block at startup. Editable as plain text, no DB round-trip required, and no schema migration when adding new tunables.

### 4.4 ESP32-CAM handling
- On ingest, detect MJPEG by extension/codec.
- Run motion detection directly on MJPEG (OpenCV handles it).
- **No re-encoding on the server in this phase.** MJPEG chunks are stored as-is. (Optional H.264 / AV1 re-encoding of long-term MJPEG storage is a future direction – see §8. AV1 is especially relevant for ESP32 footage.)

### 4.5 Metadata store
No SQLite database in this phase. The filesystem is the source of truth:

- **Sidecar JSON files** carry all chunk metadata: `chunk_id`, `camera_id`, `start_time`, `duration`, `status`, `codec`, `motion_score`, `has_motion`, `thumbnail_path`, `upload_time`. These travel with the video file as it moves from `incoming/` → `processed/` or `motionless/`.
- **Per-camera config** (`cameras.yaml` or `cameras.toml`) holds camera metadata (name, type, location) and detector parameters per §4.3. The UI reads this file at startup.
- **Directory scans** power the API:
  - The `chunks` endpoint lists files in `data/processed/<camera_id>/YYYY-MM-DD/` (date-sharded), parses the timestamp from the filename, and reads the sidecar JSON for motion flags.
  - The `chunk_exists` pre-check uses the date-shard to bound the search to a single day.
  - With 10-second chunks and a small number of cameras, this is plenty fast; no index is needed.

> **Future:** When events are added (§8), SQLite may be introduced scoped to the `events` table only. The chunk-level data remains filesystem-first, and the sidecar JSON schema is designed so a future backfill into any database is straightforward.

### 4.6 Retention / cleanup job
- New scheduled job (cron, APScheduler, or a sleep-loop worker):
  - Delete `motionless/` chunks older than N days (e.g. 7, configurable in a server config file).
  - **Do not delete `processed/` chunks automatically for now.** Motion-positive footage is kept indefinitely (or until the user manually removes it). The retention code path for processed chunks can stay in place but disabled, so it can be enabled later per camera.
- Retention windows configurable per camera.

### 4.7 (Reserved) AV1 + Immich integration – deferred
AV1/VAAPI encoding and Immich upload are **explicitly out of scope** for this phase. They will return as a follow-up:

- **AV1 re-encoding** is most relevant for ESP32-CAM MJPEG footage (and possibly long-term archival of Pi H.264), so it lands naturally alongside or after the ESP32 work.
- **Immich integration** is deprioritized for now.

The current AV1/Immich pipeline stays in the repo as opt-in (e.g. feature flags) so it isn't lost.

### 4.8 Playback API (FastAPI)
- New endpoints for the UI:
  - `GET /api/cameras` – list cameras and basic status.
  - `GET /api/cameras/{id}/chunks?start=&end=&motion_only=` – return ordered chunk playlist with URLs, timestamps, durations, thumbnails, motion flags.
  - `GET /video/{camera_id}/{filename}` – stream a chunk (supports HTTP range for scrubbing).
  - `GET /thumb/{camera_id}/{filename}` – serve a thumbnail.
- The chunk playlist is the primary view.

### 4.9 Auth
- **User auth only** for the web UI (session cookie or token from a login endpoint; basic auth is acceptable as a v1).
- **No device tokens.** Edge devices upload without any credential – the upload endpoint is open to the local network.
- User credentials stored in the server config file, not committed.

### 4.10 Framework choice – FastAPI
- Migrate the existing Flask app to **FastAPI**. Pydantic models for request/response, `BackgroundTasks` (or a real task queue later) for the motion worker, and `StreamingResponse` for chunked video. Type-driven OpenAPI docs come for free.
- The structure above is written with FastAPI in mind.

## 5. New Web UI

- New `web/` directory (served by the same backend) containing:
  - Camera list with last-seen indicator and latest thumbnail.
  - Per-camera timeline view with motion markers.
  - Playlist-based player that loads sequential chunks (HTML5 video element advancing through the list, or Media Source Extensions if seamless scrubbing is needed).
  - Filters: time range, motion-only toggle, camera selection.
  - Continuous chunk playback is the only playback path.
- Keep the stack simple (server-rendered + HTMX, or a small vanilla JS/React app) to avoid a heavy build pipeline on this repo.
- UI sits behind user auth; chunk upload itself is not gated.

## 6. Configuration + Secrets

- **Server**: one central `.env` / config file with paths, retention defaults, detector defaults, and user credentials. AV1/Immich toggles remain present but off.
- **Edge devices**: each device has a `device.yaml` as described in §2.4. `server_url` and `device_name` are required; `upload_enabled` and `upload_grace_period_seconds` cover the offline/grace-period cases.
- Document everything in the README so a fresh device or server setup is reproducible.

## 7. Migration + Cleanup

- Delete on-device motion code and services (see §2.2).
- Update `setup_local.sh` / `setup_upload.sh` to install only the new capture + uploader services. The uploader service should reference the device config file.
- Update `shutdown_services.sh` to stop both old and new service names so upgrades are clean.
- Rewrite `README.md` to reflect:
  - The new architecture (edge = dumb recorder, server = smart processor).
  - Setup steps for: server, Raspberry Pi edge device, ESP32-CAM edge device.
  - How to view footage in the new UI.
  - User auth setup for the web UI.
  - That on-device motion detection is gone, and why.
- Rename the repo (already a TODO) – something like `distributed-surveillance` since it now covers Pi + ESP32 + server + UI, not just Pi. (not yet, but eventually)
- Move existing exploratory notebooks (`motion_detection.ipynb`, `motion_calibration.ipynb`, `home_comp_av1.ipynb`, `immich_av1.ipynb`, `clip_uploader.ipynb`, `test.ipynb`) into a `notebooks/` directory, and move irrellevant ones into an `old/` subdirectory.
- Keep the existing AV1/Immich pipeline available but optional, so the user doesn't lose their current working setup during the transition.

## 8. Future Directions (Not in This Phase)

Recorded here so they don't get lost, but **explicitly deferred** until the core server + edge pipeline is working end-to-end:

- **Event handling**: contiguous-motion rollups, an `events` table, grouped events in the UI.
- **User export pipeline**: recombined / timestamp-burned downloads. Adds a `data/exports/` directory back.
- **AV1 re-encoding**: most relevant for ESP32 MJPEG archival and possibly long-term Pi storage. Will reuse the existing VAAPI pipeline.
- **Immich upload**: optional push of motion-positive chunks to Immich.
- **Auto-deletion of `processed/` chunks**: retention code path exists but is off; add per-camera retention windows when this comes back.
- **Per-camera config on the server side**: detector hints, retention overrides, etc.

## 9. Suggested Build Order

The first two phases are **server-only** and can be tested locally with simulated uploads before touching the Pi. This keeps the iteration loop tight and avoids coupling edge changes to server changes.

1. **Server: FastAPI upload endpoint + directory layout.**
   - Stand up FastAPI, the `/upload` endpoint (no auth), `data/incoming/`, `data/processed/`, `data/motionless/`, `data/thumbs/`.
   - Add `/chunk_exists`.
   - Test locally with a one-off script that pushes a fake chunk + sidecar JSON.
2. **Server: web UI + user auth.**
   - Add user login, camera list, chunk playlist view, video/thumb streaming endpoints.
   - Manually copy a couple of test chunks into `data/processed/` and confirm the UI plays them.
   - Verify end-to-end: simulated upload → incoming dir → manually promote to processed → UI shows it.
3. **Pi: capture + uploader rewrite + device config file.**
   - Switch capture to 10s timestamped chunks, write sidecar metadata.
   - Rewrite `clip_uploader.py` to read `device.yaml`, POST chunk+metadata, mark uploaded, delete after grace period.
   - Set `upload_enabled: false` in the config to validate the "no upload" path.
4. **Server: motion detection worker + processed/motionless sorting + thumbnails.**
   - Wire the worker to consume `data/incoming/`, run the existing OpenCV motion logic, and move chunks into `processed/` or `motionless/`.
   - Generate thumbnails. The motion worker writes `motion_score` and `has_motion` into the sidecar JSON; the UI reads these directly from the filesystem.
5. **ESP32-CAM: sketch + config + docs.**
   - Same upload protocol as the Pi, MJPEG-on-SD, no auth.
6. **Polish: retention job, per-camera config, rename repo, rewrite README.**

## 10. Explicitly Out of Scope

- The robotic chicken coop project stays separate. If integration is ever wanted, it's a one-way bridge (MQTT/webhook) into Home Assistant – not part of this repo.
- Frigate is not adopted; this repo intentionally builds a tailored alternative because of the offline/bulk-upload, user-auth-only, and ESP32-CAM gaps.
- See §8 for the explicit list of features deferred from this phase (events, exports, AV1, Immich, auto-deletion of processed).
