FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deno.land/install.sh | sh && \
    ln -s /root/.deno/bin/deno /usr/local/bin/deno

ENV YTDLP_EXTERNAL_JS=1

COPY . .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade yt-dlp

ENV GUNICORN_CMD_ARGS="--workers=3 --threads=2 --timeout=120"

EXPOSE 6095

CMD ["gunicorn", "--bind", "0.0.0.0:6095", "app:app"]
