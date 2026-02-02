FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

COPY butler/ ./butler/

RUN mkdir -p /app/butler/data /app/logs

CMD ["python", "-m", "butler.core.main"]
