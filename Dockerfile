FROM python:3.11-slim

# curl — runtime dep for curl_cffi + healthcheck probe
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libcurl4 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so this layer is cached between code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (see .dockerignore for exclusions)
COPY . .

# Create DB directory so the volume mount point exists in the image
RUN mkdir -p data

EXPOSE 5000

# Single worker — APScheduler runs inside the worker process
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "--timeout", "120", "wsgi:app"]
