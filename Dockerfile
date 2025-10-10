FROM python:3.11-slim

WORKDIR /app

COPY . .

# Install dependencies including Gunicorn
RUN pip install --no-cache-dir -r requirements.txt gunicorn

EXPOSE 6095

CMD ["gunicorn", "--bind", "0.0.0.0:6095", "app:app"]
