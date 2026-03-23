FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive

# Layer 1 — system deps
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev \
    libopus-dev libsodium-dev ffmpeg \
    locales \
    && locale-gen en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8

# Layer 2 — python deps
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Layer 3 — app scaffold
WORKDIR /app
COPY bot/ ./bot/
COPY main.py ./
COPY run_bot.py ./
RUN mkdir -p /app/transcript /app/tmp /app/.cache
ENV HF_HOME=/app/.cache

ARG WHISPER_MODEL=medium
ENV WHISPER_MODEL=${WHISPER_MODEL}

RUN chown -R 1000:1000 /app
USER 1000

CMD ["python3", "run_bot.py"]
