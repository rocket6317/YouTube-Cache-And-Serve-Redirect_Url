FROM python:3.13-slim

WORKDIR /app

# Install system dependencies needed for Deno and pip builds
RUN apt-get update && apt-get install -y \
    curl ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Deno (official install script downloads a static binary)
RUN curl -fsSL https://deno.land/install.sh | sh && \
    ln -s /root/.deno/bin/deno /usr/local/bin/deno

# Tell yt-dlp to use external JS runtime
ENV YTDLP_EXTERNAL_JS=1

# Copy project files
COPY . .

# Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade yt-dlp

EXPOSE 6095

CMD ["gunicorn", "--bind", "0.0.0.0:6095", "app:app"]
