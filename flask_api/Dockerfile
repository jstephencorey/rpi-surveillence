FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

CMD [ "gunicorn", "--config", "./gunicorn_config.py", "app:app"]
