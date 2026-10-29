FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl ffmpeg libespeak-ng1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/sarah
COPY requirements.txt requirements-tts.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-tts.txt

# Explicit build-time downloads, never a runtime cloud speech fallback.
ENV R1_WHISPER_MODELS=/opt/speech/whisper R1_KOKORO_ROOT=/opt/speech/kokoro
RUN python -c 'from faster_whisper.utils import download_model; download_model("base", cache_dir="/opt/speech/whisper")' \
    && mkdir -p /opt/speech/kokoro \
    && curl -fL --retry 3 https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx -o /opt/speech/kokoro/kokoro-v1.0.onnx \
    && curl -fL --retry 3 https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin -o /opt/speech/kokoro/voices-v1.0.bin \
    && printf '%s  %s\n' \
       7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5 /opt/speech/kokoro/kokoro-v1.0.onnx \
       bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d /opt/speech/kokoro/voices-v1.0.bin | sha256sum -c - \
    && ln -s /usr/local /opt/speech/kokoro/venv \
    && useradd --uid 1000 --create-home chad \
    && install -d -o chad -g chad -m 0700 /var/lib/sarah
COPY bridge/ ./bridge/
COPY --chmod=0755 docker-entrypoint.sh /usr/local/bin/sarah-start
USER chad
ENV PYTHONUNBUFFERED=1 HOME=/var/lib/sarah
ENTRYPOINT ["/usr/local/bin/sarah-start"]
CMD ["--http", "--bind", "127.0.0.1", "--port", "8789"]
