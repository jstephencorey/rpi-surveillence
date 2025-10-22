FROM nvidia/cuda:12.6.2-base-ubuntu24.04

RUN apt-get update && apt-get install -y python3 python3-pip ffmpeg && apt-get clean

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --break-system-packages -r requirements.txt
COPY . .

CMD ["gunicorn", "--config", "./gunicorn_config.py", "app:app"]

