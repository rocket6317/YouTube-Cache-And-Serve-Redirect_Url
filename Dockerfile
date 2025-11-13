FROM python:3.13-slim

WORKDIR /app

# Install Node.js 20.x for yt-dlp and required system libs
RUN apt-get update && apt-get install -y curl gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs libc6 libstdc++6 libgcc1 \
    && ln -sf /usr/bin/node /usr/bin/nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade yt-dlp

EXPOSE 6095

CMD ["gunicorn", "--bind", "0.0.0.0:6095", "app:app"]
