FROM python:3.11-slim

RUN apt update && apt install -y \
    alsa-utils libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN pip install --upgrade pip && \
    pip install websockets aiohttp python-dotenv azure-cognitiveservices-speech

CMD ["python", "ws_translator_server.py"]