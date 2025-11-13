FROM python:3.13-slim

WORKDIR /app

# Install Node.js + npm for yt-dlp JavaScript runtime
# Add symlink so yt-dlp finds "node" instead of "nodejs"
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && ln -sf /usr/bin/node /usr/bin/nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 6095

# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:6095", "app:app"]
