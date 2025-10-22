FROM jrottenberg/ffmpeg:6.1-nvidia

# Install Python
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python dependencies
COPY requirements.txt .
RUN pip3 install  --break-system-packages -r requirements.txt

# Copy the app
COPY . .

# Default command
CMD ["gunicorn", "--config", "./gunicorn_config.py", "app:app"]
