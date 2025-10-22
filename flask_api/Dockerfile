# Stage 1: get ffmpeg with hw acceleration
FROM linuxserver/ffmpeg:version-8.0-cli as ffmpeg

# Stage 2: your app
FROM python:3.11-slim

WORKDIR /app

# Copy ffmpeg binaries from the first image
COPY --from=ffmpeg /usr/bin/ffmpeg /usr/bin/ffprobe /usr/bin/

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "--config", "./gunicorn_config.py", "app:app"]