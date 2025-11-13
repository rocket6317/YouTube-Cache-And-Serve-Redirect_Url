FROM python:3.13

WORKDIR /app

# Install Node.js and npm from Debian repos
RUN apt-get update && apt-get install -y nodejs npm \
    && ln -s /usr/bin/nodejs /usr/bin/node \
    && rm -rf /var/lib/apt/lists/*

# Environment variable to tell yt-dlp to use external JS runtime
ENV YTDLP_EXTERNAL_JS=1

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade yt-dlp

EXPOSE 6095

CMD ["gunicorn", "--bind", "0.0.0.0:6095", "app:app"]
