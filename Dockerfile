FROM python:3.13-slim

WORKDIR /app

# Install curl + Node.js (from NodeSource) for yt-dlp runtime
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/node /usr/bin/nodejs || true

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 6095

CMD ["gunicorn", "--bind", "0.0.0.0:6095", "app:app"]
