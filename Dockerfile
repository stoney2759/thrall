FROM python:3.12-slim

WORKDIR /app

# Install system deps for Playwright and other native packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer cache — only rebuilds when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (used by web.browse tool)
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Expose the WebSocket / HTTP API port
EXPOSE 8000

CMD ["python", "run.py"]
