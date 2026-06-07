FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-pip ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --break-system-packages -r requirements.txt
COPY . .

CMD ["gunicorn", "--config", "./gunicorn_config.py", "app.main:app"]
